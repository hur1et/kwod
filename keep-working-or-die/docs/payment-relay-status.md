# Payment relay: development status

The internal `kwod.payment_relay` coordinator journals signing and broadcast
uncertainty, retries identical transaction bytes, serializes pending transfers,
and distinguishes inclusion from finalized transfer effects. It has no production
entry point. Quote, network broadcast and receipt verification adapters are still
required. Its default mode does not sign or broadcast.

Local transport-double tests cover restart after uncertain signing/broadcast,
disabled mode, stale unsigned quotes, immutable request IDs, queue ordering and
canonical finality. These do not validate actual cryptographic decoding or a live
Base transaction. Those checks remain outstanding before deployment.

## OpenRouter checkout observation, 2026-09-15

A user-provided Coinbase checkout visibly displayed payment of USD 10.50 to
OpenRouter, Inc and an explicit agent payment link using x402. No wallet was
connected, signature generated or payment submitted. The temporary session URL
is deliberately not stored in this document.

Coinbase documents these checkouts as gasless USDC on Base using the EVM
`auth-capture` scheme and EIP-3009 authorization. The existing ETH/USDC transfer
signer and relay cannot pay these authorizations. Do not enable arbitrary message
signing or import the project key into a browser wallet as a shortcut.

Still required: retrieve and validate the unsigned payment requirements, implement
a narrowly scoped authorization signer with durable replay handling, verify
settlement and OpenRouter credit delivery, and establish how fresh OpenRouter
checkouts can be obtained for future autonomous purchases. The visible checkout
amount alone does not establish credited compute value or the fee breakdown.

Reference: https://docs.cdp.coinbase.com/coinbase-business/checkout-apis/accept-x402-payments

## Unsigned challenge review

The user successfully ran `Check-Checkout.ps1`. The challenge requests 10,500,000
native Base USDC units, EIP-3009, fee bounds of 100 bps and collection timeout
3,600 seconds. Capture/refund deadlines are 1821005089 (2027-09-15 10:44:49 UTC).
The x402 specification distinguishes collection expiry from the later escrow
capture/reclaim expiry. The latter can leave an uncaptured hold outstanding until
that deadline. At full capture the specified fee is 105,000 USDC units taken from
the captured amount; this does not establish OpenRouter compute credit delivery.

`kwod.auth_capture.review` now validates the observed subset offline. It rejects
unknown signing-related fields, other assets/networks/domains, invalid integer
bounds and expiry order, and reports deployment conflicts. It cannot sign.

The observed extra.tokenCollector names the v1.0 collector but omits
extra.authCaptureEscrow. The current specification defaults omission to v1.1,
which uses a different collector. This requires version-specific compatibility
verification before building/signing a payload; never silently select a deployment
from an untrusted collector hint. No production service was changed.

Local verification: 26 tests and 46 subtests passed across term review, unsigned
probe, transfer relay recovery and signer journal tests. Cryptographic auth-capture
construction, signed-payload restart recovery, network settlement and compute
credit reconciliation remain unimplemented.

Protocol source inspected:
https://github.com/x402-foundation/x402/blob/main/specs/schemes/auth-capture/scheme_auth_capture_evm.md

## Development authorization constructor and journal

`auth_capture_signing.py` now constructs a narrowly scoped EIP-3009
ReceiveWithAuthorization payload for explicitly selected, consistent deployments.
It binds the payment terms into the payer-agnostic nonce, then signs in the USDC
token domain. An internal journal binds one checkout session to immutable terms,
salt and expiry before invoking the signing adapter. Completed signatures are
committed before return; retries reuse the committed result. An expired unfinished
authorization cannot silently acquire a fresh salt or expiry. No public signing
endpoint or production wiring has been added.

The supplied legacy checkout still fails the explicit-deployment requirement.
The older official nonce source confirms the hashing layout, but cached sources
from different dates do not prove the checkout backend's deployment. This remains
an integration issue, not something to resolve by guessing a contract address.

32 local tests and 46 subtests pass with signing adapters doubled. Real signature
recovery and mutation checks are in `test_auth_capture_crypto.py`, skipped when
eth-account is unavailable. They must pass in the wallet dependency environment
and be compared against an official client vector before production enablement.
No production signing, authorization transmission, payment, or agent start occurred.

Official nonce implementation inspected:
https://github.com/x402-foundation/x402/blob/main/typescript/packages/mechanisms/evm/src/auth-capture/nonce.ts

## Ubuntu crypto test runner

`deploy/Test-AuthCapture.ps1 -SshTarget s340` packages only the test and three
payment modules, verifies uploaded SHA256 hashes, and starts a transient systemd
test through `run_auth_capture_selftest.py`. It uses the existing root-controlled
signer Python environment under a DynamicUser, with IP socket creation prohibited,
private temporary storage, and the operational wallet and API-key paths inaccessible.
It installs no service and changes no signer configuration.

The test uses public key 1, checks EIP-712 signature recovery and determinism,
mutates all nonce-bound payment fields and escrow deployment, checks the payer
binding, then simulates interruption after signing and reopens the durable journal.
It emits a public test nonce/signature for later official-client comparison. This
is not yet an independent client compatibility vector.

Local syntax, bundle assembly with mocked SSH/SCP, and the existing 32 tests/46
subtests passed. The user subsequently ran the test on s340 and reported success:
real signature recovery, eleven payment-term mutations and restart replay passed.
The test reported no network use, no production-key read, no payment authorization
and no worker start. This confirms the local cryptographic selftest on Ubuntu;
it does not verify Coinbase acceptance or OpenRouter credit delivery.

The user-reported public test nonce is
`0xa1a5db58c18a88bed4c88b409e6d773633c1266e0310ca65b2cc3a5adc6183c7`.
Its signature is captured in `test_auth_capture_crypto.py` as a regression vector
from our implementation, explicitly not an independent official-client vector.
The new regression assertion remains unexecuted locally because eth-account is
unavailable here. No repeat Ubuntu invocation is needed just to record this result.

## Independent official-client comparison prepared

`Test-AuthCapture.ps1 -OfficialClient` now stages an isolated temporary comparison.
It installs @x402/evm 2.17.0 and 2.25.0 under npm aliases and viem 2.48.11, with
lifecycle scripts disabled, under an unprivileged account whose home is temporary.
No packages are added to the operational signer environment. Transitive packages
are resolved by npm during this test installation; this is not a production lockfile.
The transient services have runtime limits and cannot read operational wallet/API
key paths. Downloads use the network; the subsequent signature comparison does not.

Each official client constructs a test payload using public key 1 and synthetic
merchant/operator addresses. Python reconstructs the payload using the client's
salt and expiry, compares the complete signature/authorization payload, and reports
which deployment matches. Explicit deployment fields are added only to local test
candidates; no live checkout is modified. Matching a client does not authenticate
the current Coinbase backend or prove compute credit delivery.

Local Python/JavaScript/PowerShell syntax and bundle construction with mocked
SSH/SCP passed. The actual official packages and comparison have not run here;
the Ubuntu invocation is pending. Unsupported exports/payloads fail visibly.

## Independent official-client comparison confirmed — 2026-09-15

The user supplied the successful Ubuntu rerun: `official_client_comparison=passed`.
Both clients matched the Python authorization payload, including nonce and signature:

- @x402/evm 2.17.0 matched v1.0 and honored the legacy collector hint.
- @x402/evm 2.25.0 matched v1.1 and did not honor the legacy collector hint.

The runner reported public test key only, no signing network use, no checkout
backend verification, no payment authorization, and no worker start. This supersedes
the pending-run statement above. The successful rerun follows address-case comparison
normalization, but the earlier failure lacks field diagnostics, so its cause is not
proven. All fields other than authorization address letter case are compared strictly.

The supplied summary contains no full official payloads and cannot be used to invent
independent regression fixtures. No rerun is required merely to confirm this result.
The existing explicit, consistent deployment requirement remains in place: client
agreement verifies local construction for both deployments, not which deployment
the actual checkout backend accepts. Next resolve that backend version using unsigned
evidence; backend acceptance and OpenRouter credit reconciliation remain unverified.

## Unsigned backend evidence review — 2026-09-15

Re-read the official Coinbase checkout guide and current x402 EVM scheme after
the successful comparison. The scheme explicitly defaults absent authCaptureEscrow
to v1.1 and says collectors are resolved from that deployment. Coinbase's guide
describes the unsigned POST challenge but does not identify the deployment used by
a particular checkout. Neither source establishes which backend accepts the previously
observed legacy collector. Do not infer that from either npm client's behavior.

The actual checkout URL is absent from HANDOFF.md and has been requested from the
user. Next inspect that checkout's unsigned requirements using the existing probe;
preserve them unchanged. An explicit consistent escrow would resolve the advertised
version for local preparation only. If the same legacy hint remains, unsigned
requirements alone still do not resolve compatibility. A /supported advertisement
is not evidence tying a particular payment session to a deployment either.

Coinbase documents that HTTP 200 establishes authorization, while checkout COMPLETED
establishes settlement. Its documented Get Checkout API requires merchant credentials;
the payer must not assume access to OpenRouter's merchant API. Neither response by
itself establishes compute credits. The guide also says sandbox checkouts currently
lack an x402_url, so no sandbox compatibility run is available through that flow.

Sources inspected:
- https://docs.cdp.coinbase.com/coinbase-business/checkout-apis/accept-x402-payments
- https://raw.githubusercontent.com/x402-foundation/x402/main/specs/schemes/auth-capture/scheme_auth_capture_evm.md

This step changed documentation only. No signatures or network payment requests
were created; no production services were changed.

### Actual checkout re-probed

The user supplied the checkout URL. After a turn-scoped network permission grant,
the existing local probe successfully fetched the unsigned challenge. Unchanged
requirements and original challenge hash are in `checkout-observation-2026-09-15.json`.
The response still advertises the v1.0 collector without authCaptureEscrow.
Offline review of that saved observation returned
`collector_conflicts_with_resolved_escrow`, `deployment_explicit=false`, and
`signing_enabled=false`. No new local cryptographic defect is established by this
result. Resolution needs authoritative session-specific backend evidence; another
identical client comparison or challenge request would not supply that evidence.
No third-party contact has been authorized.
