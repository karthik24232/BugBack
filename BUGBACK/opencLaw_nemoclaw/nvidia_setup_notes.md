# NVIDIA / OpenClaw / Nemotron Setup Notes

The event deliverable asks for a working OpenClaw agent powered by NVIDIA Nemotron.

Official docs currently describe NVIDIA as an OpenAI-compatible provider for OpenClaw using:

```bash
export NVIDIA_API_KEY="nvapi-..."
openclaw onboard --auth-choice skip
openclaw models set nvidia/nvidia/nemotron-3-super-120b-a12b
```

NemoClaw can also onboard an OpenClaw agent inside a sandbox and add policy-based security controls.

Use the provided `bugback_policy.yaml` as the policy concept:
- local privacy mode
- no rollback/refund/email without approval
- browser/log/feature-flag tools allowed

The core project runs without the SDK so you can demo it immediately. During the hackathon, wire the `BugBackAgent.investigate()` method into OpenClaw as a tool or task handler.
