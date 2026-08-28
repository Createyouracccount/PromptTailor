# PromptTailor demo — rendered with VHS (https://github.com/charmbracelet/vhs)
# Re-render: vhs docs/demo.tape   (needs `claude` CLI logged in; real calls, ~20s each — waits are cut)
Output docs/demo.gif

Set Shell zsh
Set FontSize 16
Set Width 1100
Set Height 620
Set Padding 18
Set Theme "Catppuccin Mocha"
Set TypingSpeed 30ms
Env PATH "/Users/kimdu/.local/bin:/Users/kimdu/Library/Python/3.12/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
Env PROMPT_TAILOR_DATA_DIR "/tmp/prompt-tailor-demo"

Hide
Type "setopt interactivecomments; clear"
Enter
Show

Type "# 1) vague request -> rewritten for the target model (real call, ~20s wait cut)"
Enter
Sleep 500ms
Type `prompt-tailor "fix the login bug asap, users keep getting logged out" --model fable-5 --concise`
Sleep 600ms
Hide
Enter
Wait+Screen@120s /변경 요약/
Show
Sleep 7s
Screenshot docs/demo_rewrite.png

Type "clear"
Enter
Type "# 2) already-clear request -> the clarity gate returns it untouched"
Enter
Sleep 500ms
Type `prompt-tailor "In src/auth/login.py rename validate_token to validate_session_token, update its call sites, and run tests/test_auth.py" --model fable-5 --concise --json`
Sleep 600ms
Hide
Enter
Wait+Screen@120s /"changes"/
Show
Sleep 7s
Screenshot docs/demo_keep.png
