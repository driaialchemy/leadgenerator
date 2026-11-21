# Connect Gmail or Outlook

The app can save an approved note as a draft, or send it, from a mailbox you sign in to. Practice still writes a file under `outbox/` and does not email anyone.

Tokens and client files stay in `C:\Users\msell\secrets`. The app reads the first key file that exists: the path in `LEADGEN_ENV_FILE`, then `C:\Users\msell\secrets\workuity.env`, then `C:\Users\msell\secrets\leadgenerator.env`. Put the lines below in that file. Do not commit the file, the client file, or a token.

## Gmail

1. Open [Google Cloud Console](https://console.cloud.google.com/) and create a project, or pick one you already use for this demo.
2. Enable the Gmail API for that project: APIs & Services → Library → Gmail API → Enable.
3. Configure the OAuth consent screen. Choose External, add yourself as a test user, and add the scope `https://www.googleapis.com/auth/gmail.compose`. That scope creates drafts and sends mail. It does not include read access to the mailbox.
4. Create an OAuth client: APIs & Services → Credentials → Create credentials → OAuth client ID. Application type is Desktop app.
5. Download the JSON and save it outside the repo, for example `C:\Users\msell\secrets\gmail-client.json`.
6. Add these lines to the key file. The token file does not exist yet. The app creates it the first time you press Connect.

```
LEADGEN_GMAIL_CLIENT_FILE=C:\Users\msell\secrets\gmail-client.json
LEADGEN_GMAIL_TOKEN_FILE=C:\Users\msell\secrets\gmail-token.json
```

7. On the class page, open Settings and press Connect next to Gmail. Sign in with the Google account that should own the drafts. Settings then shows Connected and that address.

The app asks Google for only `https://www.googleapis.com/auth/gmail.compose`.

## Outlook

1. Open [Microsoft Entra admin center](https://entra.microsoft.com/) → App registrations → New registration.
2. Name the app. Supported account types: personal Microsoft accounts, or accounts in any directory and personal accounts, if this mailbox is an Outlook.com account.
3. Redirect URI: Public client/native (mobile & desktop), `http://localhost`.
4. After it is created, open Authentication and set Allow public client flows to Yes. Leave the redirect as `http://localhost`. Do not create a client secret. This is a public client.
5. API permissions → Add a permission → Microsoft Graph → Delegated permissions. Add exactly these two:
   - `Mail.Send`
   - `Mail.ReadWrite`
6. `Mail.ReadWrite` is what Graph requires to create a draft. That permission can also read mail. This app never lists or reads messages. It only creates a draft and, when you confirm, sends that draft.
7. Copy the Application (client) ID. Add these lines to the key file. Use `consumers` for a personal Outlook.com account. Use `common` if the account is work or school and personal accounts are both allowed on the app.

```
LEADGEN_OUTLOOK_CLIENT_ID=paste-the-application-id-here
LEADGEN_OUTLOOK_TOKEN_FILE=C:\Users\msell\secrets\outlook-token.json
LEADGEN_OUTLOOK_TENANT=consumers
```

8. On Settings, press Connect next to Outlook and sign in. Settings shows Connected and the signed-in address.

The app requests only `Mail.Send` and `Mail.ReadWrite`.

## After you connect

Demo safety is on until you turn it off in Settings. Send now then reaches only an address or domain on `allowlist` in `config/pipeline.yaml`, or the signed-in account itself. Save as draft is still available for other addresses. Send now also stops after `send_cap` messages in that session. The default cap is 5.

Disconnect deletes the token file named above. It does not delete the Google client file or the Entra app.

A full walk of the safeguards is in the README.
