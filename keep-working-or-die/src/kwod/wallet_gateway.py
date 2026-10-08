"""Production Base ETH/USDC transfers through the isolated durable signer."""
import json
from pathlib import Path
import socket
import time

import httpx
from .autonomy import require
from .assets import quantity
from .payments import CHAIN_ID, USDC, SOCKET, PaymentError, transaction
from .payment_relay import PaymentRelay, receipt_observation

ORACLE = '0x420000000000000000000000000000000000000F'


def signer(request):
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as conn:
        conn.settimeout(20); conn.connect(SOCKET)
        conn.sendall(json.dumps(request).encode()+b'\n')
        with conn.makefile('rb') as stream: raw=stream.readline(16385)
    if len(raw)>16384 or not raw.endswith(b'\n'): raise PaymentError('invalid_signer_reply')
    value=json.loads(raw)
    if value.get('ok') is not True: raise PaymentError('signer_rejected')
    return value


class BaseRPC:
    def __init__(self, address, client): self.address,self.client=address,client

    def rpc(self, method, params):
        result=self.client.post('https://mainnet.base.org',json={'jsonrpc':'2.0','id':1,'method':method,'params':params})
        if result.status_code!=200 or len(result.content)>262144: raise PaymentError('rpc_unavailable')
        value=result.json()
        if value.get('id')!=1 or 'error' in value or 'result' not in value: raise PaymentError('rpc_rejected')
        return value['result']

    def chain(self):
        if quantity(self.rpc('eth_chainId',[]))!=CHAIN_ID: raise PaymentError('wrong_chain')

    def oracle(self, signature, number, block):
        from eth_utils import keccak
        data='0x'+keccak(text=signature)[:4].hex()+format(number,'064x')
        return quantity(self.rpc('eth_call',[{'to':ORACLE,'data':data},block]))

    def quote(self, intent):
        self.chain()
        block=self.rpc('eth_blockNumber',[]); quantity(block)
        nonce=quantity(self.rpc('eth_getTransactionCount',[self.address,'pending']))
        # An outside wallet spend must settle before this single-writer relay signs.
        if nonce!=quantity(self.rpc('eth_getTransactionCount',[self.address,'latest'])):
            raise PaymentError('wallet_has_pending_transaction')
        tip=quantity(self.rpc('eth_maxPriorityFeePerGas',[]))
        price=quantity(self.rpc('eth_gasPrice',[]))
        args=dict(intent,nonce=nonce,gas=21000,max_fee_per_gas=max(1,price*2+tip),max_priority_fee_per_gas=tip)
        tx=transaction(args)
        call={'from':self.address,'to':tx['to'],'value':hex(tx['value']),'data':tx['data']}
        gas=quantity(self.rpc('eth_estimateGas',[call]))
        args['gas']=max(21000,(gas*120+99)//100)
        if intent['asset']=='USDC':
            success=quantity(self.rpc('eth_call',[call,block]))
            if success!=1: raise PaymentError('token_transfer_simulation_failed')
        # A conservative 512-byte bound covers these fixed type-2 transfers.
        l1=self.oracle('getL1FeeUpperBound(uint256)',512,block)*2
        operator=self.oracle('getOperatorFee(uint256)',args['gas'],block)*2
        return {'arguments':args,'observed_at':int(time.time()),
                'eth_balance_wei':quantity(self.rpc('eth_getBalance',[self.address,block])),
                'usdc_balance_units':quantity(self.rpc('eth_call',[{'to':USDC,'data':'0x70a08231'+self.address[2:].lower().zfill(64)},block])),
                'l1_fee_reserve_wei':l1,'operator_fee_reserve_wei':operator}

    def broadcast(self, raw):
        require('payments'); self.chain()
        return self.rpc('eth_sendRawTransaction',[raw])

    def observe(self, tx_hash, intent, address):
        self.chain()
        receipt=self.rpc('eth_getTransactionReceipt',[tx_hash])
        if receipt is None: return None
        canonical=self.rpc('eth_getBlockByNumber',[receipt['blockNumber'],False])
        finalized=self.rpc('eth_getBlockByNumber',['finalized',False])
        tx=self.rpc('eth_getTransactionByHash',[tx_hash])
        effect=transfer_effect(tx,receipt,intent,address)
        # Missing rollup fee data remains unknown, never becomes zero.
        fee=None
        if all(k in receipt for k in ('gasUsed','effectiveGasPrice','l1Fee','operatorFee')):
            fee=quantity(receipt['gasUsed'])*quantity(receipt['effectiveGasPrice'])+quantity(receipt['l1Fee'])+quantity(receipt['operatorFee'])
        return receipt_observation(receipt,transaction_hash=tx_hash,canonical_hash=canonical['hash'],
            finalized_number=quantity(finalized['number']),effect_verified=effect,network_fee_wei=fee)


def transfer_effect(tx, receipt, intent, address):
    if not tx or tx.get('from','').lower()!=address.lower(): return False
    if tx.get('hash')!=receipt.get('transactionHash') or tx.get('blockHash')!=receipt.get('blockHash'): return False
    if intent['asset']=='ETH':
        return (tx.get('to','').lower()==intent['recipient'].lower() and
                quantity(tx['value'])==int(intent['amount_units']) and tx.get('input')=='0x')
    from eth_utils import keccak
    expected='0xa9059cbb'+intent['recipient'][2:].lower().zfill(64)+format(int(intent['amount_units']),'064x')
    if tx.get('to','').lower()!=USDC.lower() or tx.get('input','').lower()!=expected or quantity(tx['value'])!=0:
        return False
    topics=['0x'+keccak(text='Transfer(address,address,uint256)').hex(),
            '0x'+address[2:].lower().zfill(64),'0x'+intent['recipient'][2:].lower().zfill(64)]
    return any(log.get('address','').lower()==USDC.lower() and
               [x.lower() for x in log.get('topics',[])]==topics and
               log.get('transactionHash')==tx['hash'] and not log.get('removed',False) and
               quantity(log['data'])==int(intent['amount_units']) for log in receipt.get('logs',[]))


def execute(root, tool, args):
    require('payments')
    identity=signer({'method':'status','arguments':{}})
    if not identity['signing_enabled'] or identity['chain_id']!=CHAIN_ID: raise PaymentError('signer_not_enabled')
    with httpx.Client(trust_env=False,follow_redirects=False,timeout=20) as client:
        rpc=BaseRPC(identity['address'],client)
        relay=PaymentRelay(Path(root)/'private/payment-relay',identity['address'],
            quote=rpc.quote,sign=signer,broadcast=rpc.broadcast,observe=rpc.observe,enabled=tool=='wallet_transfer')
        try:
            if tool=='wallet_transfer': relay.enqueue(args)
            # Each transition is durable. Receipt-only inspection never signs or sends.
            for _ in range(4 if tool=='wallet_transfer' else 1):
                result=relay.advance(args['request_id'])
                if result['state'] in ('submitted','included','finalized','reverted','recovery_required'): break
            row=relay.db.execute('SELECT signed FROM payments WHERE id=?',(args['request_id'],)).fetchone()
            return {'ok':True,**result,'transaction_hash':json.loads(row['signed'])['transaction_hash'] if row['signed'] else None,
                    'receipt_confirmed':result['state']=='finalized','chain_id':CHAIN_ID}
        finally: relay.close()
