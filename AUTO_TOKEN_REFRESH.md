# Automatic BD JWT Token Refresh

This project refreshes all tokens from `Uid_bd.json` automatically using Dual Speed APIs:

1. `https://flash-token-api.vercel.app/token?uid={uid}&password={password}&key=Flash` (Starts from beginning)
2. `https://flash-token-v2.vercel.app/token?uid={uid}&password={password}&key=Flash` (Starts from end)

The response field used is `Token` (OB55 full JWT). The generated tokens are automatically saved to `token_bd.json`.

Keep the repository private because `Uid_bd.json` contains credentials.