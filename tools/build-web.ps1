param(
    [string]$UnityPath = 'C:/Users/gksix/Unity/Hub/Editor/6000.3.19f1/Editor/Unity.exe'
)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
$workRoot = Join-Path $repoRoot '.web-build-work'
$nativeOutput = Join-Path $workRoot 'export'
$webOutput = Join-Path $repoRoot 'web'
$logPath = Join-Path $workRoot 'web-build.log'
if (-not (Test-Path -LiteralPath $UnityPath)) { throw 'Unity editor not found.' }
if (-not (Test-Path -LiteralPath (Join-Path (Split-Path $UnityPath -Parent) 'Data/PlaybackEngines/WebGLSupport'))) { throw 'Install WebGL Build Support first.' }
New-Item -ItemType Directory -Path $workRoot,$webOutput -Force | Out-Null
if (Test-Path -LiteralPath $nativeOutput) {
    $resolvedOutput = (Resolve-Path -LiteralPath $nativeOutput).ProviderPath
    $resolvedWork = (Resolve-Path -LiteralPath $workRoot).ProviderPath
    if (-not $resolvedOutput.StartsWith($resolvedWork + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase) -or ((Get-Item -LiteralPath $nativeOutput).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw 'Generated export path is outside the isolated build workspace.'
    }
    Remove-Item -LiteralPath $resolvedOutput -Recurse -Force
}
foreach ($folder in @('Assets','Packages','ProjectSettings')) {
    $source = Join-Path $repoRoot "YugiriVillage/$folder"
    $destination = Join-Path $workRoot $folder
    robocopy $source $destination /E /R:1 /W:1 /NFL /NDL /NJH /NJS /NP | Out-Null
    if ($LASTEXITCODE -gt 7) { throw "Project copy failed: $folder" }
}
$editorFolder = Join-Path $workRoot 'Assets/Editor'
$runtimeFolder = Join-Path $workRoot 'Assets/Scripts'
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'WebBuild.cs') -Destination (Join-Path $editorFolder 'YugiriWebBuild.cs') -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'WebRuntime.cs') -Destination (Join-Path $runtimeFolder 'YugiriWebRuntime.cs') -Force
$resourcesFolder = Join-Path $workRoot 'Assets/Resources'
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'web-font/YugiriWebFont.otf') -Destination (Join-Path $resourcesFolder 'YugiriWebFont.otf') -Force
$controllerPath = Join-Path $runtimeFolder 'YugiriFirstPersonController.cs'
$controllerSource = Get-Content -LiteralPath $controllerPath -Raw
$fontPatch = @'
            InitStyles();
#if UNITY_WEBGL && !UNITY_EDITOR
            var webFont = Resources.Load<Font>("YugiriWebFont");
            if (webFont != null)
            {
                _promptStyle.font = webFont;
                _titleStyle.font = webFont;
                _subtitleBoxStyle.font = webFont;
                _hudHintStyle.font = webFont;
            }
#endif
'@
if (-not $controllerSource.Contains('            InitStyles();')) { throw 'GUI font patch anchor not found.' }
$controllerSource.Replace('            InitStyles();',$fontPatch) | Set-Content -LiteralPath $controllerPath -Encoding utf8 -NoNewline
$env:YUGIRI_WEB_OUTPUT = $nativeOutput
$env:EMCC_CORES = '2'
$env:IL2CPP_MAX_THREADS = '2'
$arguments = @('-batchmode','-nographics','-quit','-projectPath',('"' + $workRoot + '"'),'-buildTarget','WebGL','-job-worker-count','2','-background-job-worker-count','2','-gc-helper-count','1','-executeMethod','Yugiri.WebExport.WebBuild.Build','-logFile',('"' + $logPath + '"'))
$buildProcess = Start-Process -FilePath $UnityPath -ArgumentList $arguments -WindowStyle Hidden -PassThru
$buildProcess.ProcessorAffinity = [intptr]5
$buildProcess.PriorityClass = 'BelowNormal'
Write-Output "UNITY_BUILD_PID=$($buildProcess.Id)"
Write-Output "UNITY_BUILD_LOG=$logPath"
[ordered]@{pid=$buildProcess.Id;log=$logPath;output=$nativeOutput} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $workRoot 'process.json') -Encoding utf8
while (-not $buildProcess.WaitForExit(5000)) {
    # Child compilers inherit affinity. Reapply to descendants that override it.
    $allProcesses = @(Get-CimInstance Win32_Process)
    $ownedIds = [System.Collections.Generic.HashSet[int]]::new()
    [void]$ownedIds.Add($buildProcess.Id)
    do {
        $added = $false
        foreach ($item in $allProcesses) {
            if ($ownedIds.Contains([int]$item.ParentProcessId) -and -not $ownedIds.Contains([int]$item.ProcessId)) {
                [void]$ownedIds.Add([int]$item.ProcessId)
                $added = $true
            }
        }
    } while ($added)
    foreach ($ownedId in $ownedIds) {
        try {
            $child = Get-Process -Id $ownedId -ErrorAction Stop
            $child.ProcessorAffinity = [intptr]5
            $child.PriorityClass = 'BelowNormal'
        } catch { }
    }
}
$buildProcess.Refresh()
if ($buildProcess.ExitCode -ne 0) {
    Get-Content -LiteralPath $logPath -Tail 60
    throw "Unity build exited with $($buildProcess.ExitCode)."
}
$buildFolder = Join-Path $nativeOutput 'Build'
if (-not (Test-Path -LiteralPath $buildFolder)) { throw 'Unity did not produce a Build folder.' }
Copy-Item -LiteralPath $buildFolder -Destination $webOutput -Recurse -Force
$currentFiles = @(Get-ChildItem -LiteralPath $buildFolder -File | Select-Object -ExpandProperty Name)
Get-ChildItem -LiteralPath (Join-Path $webOutput 'Build') -File | Where-Object { $currentFiles -notcontains $_.Name } | ForEach-Object { Remove-Item -LiteralPath $_.FullName -Force }
$streamingAssets = Join-Path $nativeOutput 'StreamingAssets'
if (Test-Path -LiteralPath $streamingAssets) {
    Copy-Item -LiteralPath $streamingAssets -Destination $webOutput -Recurse -Force
}
$loader = @(Get-ChildItem -LiteralPath $buildFolder -File -Filter '*.loader.js')
$framework = @(Get-ChildItem -LiteralPath $buildFolder -File -Filter '*.framework.js.gz')
$wasm = @(Get-ChildItem -LiteralPath $buildFolder -File -Filter '*.wasm.gz')
$data = @(Get-ChildItem -LiteralPath $buildFolder -File -Filter '*.data.gz')
foreach ($items in @($loader,$framework,$wasm,$data)) { if ($items.Count -ne 1) { throw 'Expected one file for each web build component.' } }
$buildConfiguration = [ordered]@{loaderUrl="Build/$($loader[0].Name)";dataUrl="Build/$($data[0].Name)";frameworkUrl="Build/$($framework[0].Name)";codeUrl="Build/$($wasm[0].Name)";companyName='Yugiri Village';productName='Yugiri Village';productVersion='1.0'} | ConvertTo-Json
[IO.File]::WriteAllText((Join-Path $webOutput 'build-config.json'), ($buildConfiguration.Replace([string][char]13, '') + [char]10), [Text.UTF8Encoding]::new($false))
node (Join-Path $PSScriptRoot 'verify-web-build.mjs')
if ($LASTEXITCODE -ne 0) { throw 'Web build validation failed.' }
Write-Output 'WEB_BUILD_COMPLETE'
