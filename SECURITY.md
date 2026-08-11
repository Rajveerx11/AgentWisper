# Security Policy

AgentWisper handles microphone audio, clipboard writes, API keys, local
repository names, and transcript history. Security reports are treated as
private by default.

## Supported versions

| Version | Supported |
| --- | --- |
| Latest `main` and latest release | Yes |
| Older releases | Best effort only |

## Report a vulnerability

Do not publish exploit details, secrets, transcripts, or private paths in a
public issue.

1. Use **Report a vulnerability** under the repository's Security tab when the
   private reporting option is available.
2. If private reporting is unavailable, open a public issue containing only a
   request for a private maintainer contact. Do not include technical details.
3. Include affected versions, reproduction conditions, impact, and a minimal
   proof of concept only after a private channel is established.

No response-time or remediation-time SLA is currently promised. Please allow
the maintainer to confirm the issue before public disclosure.

## Security boundaries

- Local Parakeet audio is processed in memory on the PC.
- Selecting a cloud provider sends recorded audio to that provider.
- API keys are encrypted for the current Windows user with DPAPI.
- Project vocabulary and learned corrections are applied locally after
  transcription and are not included in cloud prompts.
- Custom provider URLs require HTTPS except for `localhost`.
- Clipboard restoration is best effort and depends on the active application.
- DPAPI does not protect against malware already running as the same Windows
  user.
- AgentWisper does not sandbox or secure the selected repository; it only reads
  bounded manifest and filename metadata and never executes repository content.

## Secrets in reports

Revoke any exposed provider key immediately. Remove secrets and private data
from screenshots, logs, crash reports, and reproduction repositories.

