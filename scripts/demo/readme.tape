# GIF curto do README: o painel e a documentação que mente. Correr: scripts/demo-video.sh gif
Output site/public/img/localalibiscan-demo.gif

Set Shell zsh
Set Width 1300
Set Height 720
Set FontSize 15
Set Padding 20
Set Theme "Catppuccin Mocha"
Set TypingSpeed 35ms
Set WaitTimeout 120s
Set WaitPattern /projects \$$/

Hide
Type "source ~/.zshrc && clear" Enter
Sleep 1s
Show
Type "las dashboard ~/projects" Sleep 400ms Enter
Wait
Sleep 5s
Hide
Type "clear" Enter
Show
Type "las scan notes-api --only db,docs-vs-code --evidence" Sleep 400ms Enter
Wait
Sleep 6s
