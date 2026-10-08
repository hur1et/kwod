# Support request — ready to send, not sent

To: support@openrouter.ai
Subject: Coinbase x402 checkout: legacy collector conflicts with current client deployment

Hello OpenRouter Support,

I am implementing programmatic USDC credit purchases using my own wallet. Before submitting a payment, I need clarification about the contract deployment expected by this OpenRouter Coinbase checkout:

https://payments.coinbase.com/payment-sessions/paymentSession_20316d65-a8dd-47bd-ad2d-9e595f080293

An unsigned request on 15 September 2026 returned x402 v2, auth-capture, Base (eip155:8453), native USDC, amount 10500000, and:

- extra.tokenCollector: 0x0E3dF9510de65469C4518D7843919c0b8C7A7757 (v1.0)
- extra.authCaptureEscrow: absent
- maxTimeoutSeconds: 3600
- captureDeadline and refundDeadline: 1821005089

The current x402 specification defaults an absent authCaptureEscrow to v1.1. In isolated tests using only a public test key and synthetic merchant addresses, @x402/evm 2.17.0 produced a v1.0 payload, while 2.25.0 produced a v1.1 payload despite the legacy collector hint. Our independent implementation matched the nonce and signature for each respective deployment. These tests did not submit either payload to the checkout.

Could your payments team, or your Coinbase integration contact, please confirm:

1. Which exact escrow and collector addresses does this payment session expect? Is the legacy hint intentional, or should the checkout explicitly advertise authCaptureEscrow? Which client version/configuration is supported?
2. What supported payer-facing method can confirm that a completed payment has credited my OpenRouter account, without access to your Coinbase merchant credentials?
3. Is there a supported API to create subsequent crypto credit checkouts programmatically?

No payment signature has been submitted and no funds have been sent for this checkout. This is a compatibility question before payment, not a missing-credit or refund claim.

Thank you.

---

Internal notes (omit when sending):
- Support address verified at https://openrouter.ai/docs/faq on 2026-09-15.
- Spec: https://github.com/x402-foundation/x402/blob/main/specs/schemes/auth-capture/scheme_auth_capture_evm.md
- Exact observed requirements: checkout-observation-2026-09-15.json.
- No published resolution found in the searches performed; that is not proof none exists.
- Send via private support, not as a public issue with the session URL.
