$r="E:\AnatomyFactory\out\smile_explainer"; $td="$r\transparent"; $clips="$r\clips"
New-Item -ItemType Directory -Force -Path $clips | Out-Null
for($i=0;$i -lt 150;$i++){
  $n=(Get-ChildItem "$td\*.png" -ErrorAction SilentlyContinue).Count
  $bl=Get-Process blender -ErrorAction SilentlyContinue
  if($n -ge 60){ break }
  if(-not $bl -and $n -ge 2){ break }
  Start-Sleep -Seconds 10
}
$n=(Get-ChildItem "$td\*.png" -ErrorAction SilentlyContinue).Count
Write-Output ("FRAMES_READY " + $n + "/60")
$fps=24
& ffmpeg -y -framerate $fps -i "$td\frame_%04d.png" -vf "scale=1080:1920,format=yuv420p" -c:v libx264 -crf 19 -pix_fmt yuv420p "$clips\smile_explainer_vertical.mp4" 2>$null
& ffmpeg -y -framerate $fps -i "$td\frame_%04d.png" -vf "scale=1080:1920,crop=1080:1080:0:360,format=yuv420p" -c:v libx264 -crf 19 -pix_fmt yuv420p "$clips\smile_explainer_square.mp4" 2>$null
& ffmpeg -y -framerate $fps -i "$td\frame_%04d.png" -c:v prores_ks -profile:v 4444 -pix_fmt yuva444p10le "$clips\smile_explainer_alpha.mov" 2>$null
Get-ChildItem $clips | ForEach-Object { Write-Output ("CLIP "+$_.Name+" "+[math]::Round($_.Length/1KB,0)+"KB") }
Write-Output "ASSEMBLE_DONE"
