# Daily arXiv-to-Podcast Pipeline Plan

1. Fetch the latest iArxiv daily email from Gmail using query:
   - `from:noreply@iarxiv.org subject:"IArxiv.org - Daily papers"`
2. Parse the HTML ranked rows and extract visible arXiv IDs from lines like:
   - `[1] ... >2604.14282</a> (hep-ph) [score: 0.72]`
3. Select the top 10 IDs by rank order.
4. Build direct PDF URLs:
   - `https://arxiv.org/pdf/<id>.pdf`
5. Download and validate PDFs in `runs/YYYY-MM-DD/papers/`.
6. Create a NotebookLM notebook via Playwright automation.
7. Upload `00_instructions.txt` first, then all 10 PDFs.
8. Trigger Audio Overview generation.
9. If login is required, prefill email/password from `harvardkey_credentials.json` and wait for manual 2FA completion.
10. Save run metadata in `runs/YYYY-MM-DD/manifest.json` and update `state/latest_run.json`.
11. Provide cleanup command to delete downloaded files only.
12. Provide cleanup command to delete the created NotebookLM notebook.
