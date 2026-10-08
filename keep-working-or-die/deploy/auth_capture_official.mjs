// Public test identity only. Executed inside the networkless comparison sandbox.
import { privateKeyToAccount } from 'viem/accounts';
const account = privateKeyToAccount('0x' + '00'.repeat(31) + '01');
const input = JSON.parse(process.argv[2]);
const results = [];
for (const [name, version] of [['x402legacy', '2.17.0'], ['x402current', '2.25.0']]) {
  const { AuthCaptureEvmScheme } = await import(`${name}/auth-capture/client`);
  let captured;
  const signer = {
    address: account.address,
    async signTypedData(data) {
      if (captured) throw new Error('Unexpected second signature request');
      captured = data;
      return account.signTypedData(data);
    },
  };
  const result = await new AuthCaptureEvmScheme(signer).createPaymentPayload(2, input);
  if (!captured || !result?.payload?.authorization || !result.payload.salt) {
    throw new Error(`Unsupported client result in ${version}`);
  }
  results.push({version, captured, payload: result.payload});
}
console.log(JSON.stringify(results, (_, value) => typeof value === 'bigint' ? value.toString() : value));
