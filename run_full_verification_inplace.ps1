[CmdletBinding()]
param(
    [string]$RepoPath = "E:\repo\mechcad-harness",

    [string]$OutputRoot = "",

    [string]$ExpectedHead = "4675c6cdaaf63c817719db356b05f30175071081",

    [string]$PythonExe = "",

    [string]$FreeCADCmd = "",

    [string]$GmshExe = "",

    [string]$CalculixExe = "",

    [string[]]$OnlyStages = @()
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Resolve-FullPath([string]$Path) {
    return (Resolve-Path -LiteralPath $Path).Path
}

function Resolve-OptionalExecutable {
    param(
        [string]$Explicit,
        [string]$EnvironmentValue,
        [string[]]$CommandNames,
        [string[]]$DefaultPaths = @()
    )
    if (-not [string]::IsNullOrWhiteSpace($Explicit) -and (Test-Path -LiteralPath $Explicit)) {
        return (Resolve-Path -LiteralPath $Explicit).Path
    }
    if (-not [string]::IsNullOrWhiteSpace($EnvironmentValue) -and (Test-Path -LiteralPath $EnvironmentValue)) {
        return (Resolve-Path -LiteralPath $EnvironmentValue).Path
    }
    foreach ($name in $CommandNames) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($null -ne $cmd) { return $cmd.Source }
    }
    foreach ($candidate in $DefaultPaths) {
        if (Test-Path -LiteralPath $candidate) { return (Resolve-Path -LiteralPath $candidate).Path }
    }
    return ""
}

$RepoPath = Resolve-FullPath $RepoPath
if (-not (Test-Path -LiteralPath (Join-Path $RepoPath ".git"))) {
    throw "RepoPath is not a Git working tree: $RepoPath"
}

$sourceHead = (& git -C $RepoPath rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) { throw "Unable to resolve source HEAD" }
if ($sourceHead -ne $ExpectedHead) {
    throw "Fail-closed baseline mismatch. Expected $ExpectedHead but source HEAD is $sourceHead"
}

$worktree = $RepoPath
$worktreeHead = $sourceHead
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
    $OutputRoot = Join-Path $RepoPath ".verification-runs"
}
if (-not [System.IO.Path]::IsPathRooted($OutputRoot)) {
    $OutputRoot = Join-Path $RepoPath $OutputRoot
}
New-Item -ItemType Directory -Force -Path $OutputRoot | Out-Null
$OutputRoot = (Resolve-Path -LiteralPath $OutputRoot).Path

$runRoot = Join-Path $OutputRoot ("full-m0-m13-{0}-{1}" -f $timestamp, $sourceHead.Substring(0,12))
$logs = Join-Path $runRoot "logs"
$meta = Join-Path $runRoot "meta"
$artifacts = Join-Path $runRoot "artifacts"
$selectorDir = Join-Path $meta "selectors"
New-Item -ItemType Directory -Force -Path $runRoot,$logs,$meta,$artifacts,$selectorDir | Out-Null

# Record the exact in-place byte state. No checkout/reset/clean/clone is performed.
& git -C $RepoPath status --porcelain=v2 --branch --untracked-files=all 2>&1 | Out-File -Encoding utf8 (Join-Path $meta "initial_git_status.txt")
& git -C $RepoPath show -s --format=fuller HEAD 2>&1 | Out-File -Encoding utf8 (Join-Path $meta "source_commit.txt")
& git -C $RepoPath diff --binary HEAD 2>&1 | Out-File -Encoding utf8 (Join-Path $meta "initial_worktree_diff.patch")
& git -C $RepoPath diff --cached --binary HEAD 2>&1 | Out-File -Encoding utf8 (Join-Path $meta "initial_index_diff.patch")
& git -C $RepoPath ls-files -s 2>&1 | Out-File -Encoding utf8 (Join-Path $meta "tracked_index_manifest.txt")

$initialTrackedDirty = [bool](-not [string]::IsNullOrWhiteSpace((& git -C $RepoPath status --porcelain=v1 --untracked-files=no | Out-String).Trim()))
$untrackedRelevant = @(& git -C $RepoPath ls-files --others --exclude-standard -- src tests config pyproject.toml README.md AGENTS.md docs/architecture docs/reference 2>$null)
$untrackedRelevant | Out-File -Encoding utf8 (Join-Path $meta "initial_relevant_untracked.txt")

$historicalMini = Join-Path $RepoPath "projects\mini_rotary_fixture"
@(
    "mode=IN_PLACE"
    "repo=$RepoPath"
    "head=$sourceHead"
    "only_stages=$($OnlyStages -join ',')"
    "tracked_dirty_at_start=$initialTrackedDirty"
    "relevant_untracked_count=$($untrackedRelevant.Count)"
    "output_root=$OutputRoot"
    "historical_mini_path=$historicalMini"
    "historical_mini_exists=$(Test-Path -LiteralPath $historicalMini)"
    "historical_mini_reused=False"
    "repo_clone_created=False"
    "checkout_reset_clean_performed=False"
) | Out-File -Encoding utf8 (Join-Path $meta "in_place_baseline.txt")

$worktreeHead | Out-File -Encoding ascii (Join-Path $meta "worktree_commit.txt")

$script:Results = @()
function Add-Result {
    param(
        [string]$Name,
        [string]$Milestone,
        [bool]$RequiredForMilestone,
        [string]$Status,
        [int]$ExitCode,
        [datetime]$Started,
        [datetime]$Ended,
        [string]$LogPath,
        [string]$Note = "",
        [Nullable[int]]$Tests = $null,
        [Nullable[int]]$Failures = $null,
        [Nullable[int]]$Errors = $null,
        [Nullable[int]]$Skipped = $null
    )
    $script:Results += [pscustomobject]@{
        stage = $Name
        milestone = $Milestone
        required_for_milestone = $RequiredForMilestone
        status = $Status
        exit_code = $ExitCode
        tests = $Tests
        failures = $Failures
        errors = $Errors
        skipped = $Skipped
        started_utc = $Started.ToUniversalTime().ToString("o")
        ended_utc = $Ended.ToUniversalTime().ToString("o")
        duration_seconds = [math]::Round(($Ended - $Started).TotalSeconds, 3)
        log = $LogPath
        note = $Note
    }
    $script:Results | Export-Csv -NoTypeInformation -Encoding utf8 (Join-Path $meta "results.csv")
}

function Invoke-ExternalStep {
    param(
        [string]$Name,
        [string]$Exe,
        [string[]]$Arguments,
        [string]$Milestone = "GLOBAL",
        [bool]$RequiredForMilestone = $false,
        [string]$AcceptNonzeroOutputPattern = ""
    )
    $logPath = Join-Path $logs ("{0}.log" -f $Name)
    $started = Get-Date
    "=== $Name ===" | Tee-Object -FilePath $logPath
    "milestone: $Milestone" | Tee-Object -FilePath $logPath -Append
    "UTC start: $($started.ToUniversalTime().ToString('o'))" | Tee-Object -FilePath $logPath -Append
    "cwd: $worktree" | Tee-Object -FilePath $logPath -Append
    "command: $Exe $($Arguments -join ' ')" | Tee-Object -FilePath $logPath -Append
    Push-Location $worktree
    $launchFailed = $false
    $output = @()
    $previousErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $output = @(& $Exe @Arguments 2>&1 | Tee-Object -FilePath $logPath -Append)
        $code = $LASTEXITCODE
    }
    catch {
        $_ | Out-String | Tee-Object -FilePath $logPath -Append
        $code = 9001
        $launchFailed = $true
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
        Pop-Location
    }
    $ended = Get-Date
    "UTC end: $($ended.ToUniversalTime().ToString('o'))" | Tee-Object -FilePath $logPath -Append
    "exit_code: $code" | Tee-Object -FilePath $logPath -Append
    $outputText = $output -join [Environment]::NewLine
    if ($launchFailed) {
        $status = "BLOCKED"
        $note = "external command could not be launched"
    }
    elseif ($code -eq 0) {
        $status = "PASS"
        $note = ""
    }
    elseif (-not [string]::IsNullOrWhiteSpace($AcceptNonzeroOutputPattern) -and $outputText -match $AcceptNonzeroOutputPattern) {
        $status = "PASS"
        $note = "recognized version output despite exit code $code; this identity probe does not replace required live execution"
    }
    else {
        $status = "FAIL"
        $note = "external command returned nonzero"
    }
    Add-Result -Name $Name -Milestone $Milestone -RequiredForMilestone $RequiredForMilestone -Status $status -ExitCode $code -Started $started -Ended $ended -LogPath $logPath -Note $note
    return $code
}

function Add-BlockedStage {
    param(
        [string]$Name,
        [string]$Milestone,
        [string]$Reason,
        [bool]$RequiredForMilestone = $true
    )
    $started = Get-Date
    $logPath = Join-Path $logs ("{0}.log" -f $Name)
    "BLOCKED: $Reason" | Out-File -Encoding utf8 $logPath
    $ended = Get-Date
    Add-Result -Name $Name -Milestone $Milestone -RequiredForMilestone $RequiredForMilestone -Status "BLOCKED" -ExitCode 127 -Started $started -Ended $ended -LogPath $logPath -Note $Reason
}

function Add-NotRunStage {
    param(
        [string]$Name,
        [string]$Milestone,
        [string]$Reason,
        [bool]$RequiredForMilestone = $false
    )
    $started = Get-Date
    $logPath = Join-Path $logs ("{0}.log" -f $Name)
    "NOT_RUN: $Reason" | Out-File -Encoding utf8 $logPath
    $ended = Get-Date
    Add-Result -Name $Name -Milestone $Milestone -RequiredForMilestone $RequiredForMilestone -Status "NOT_RUN" -ExitCode 0 -Started $started -Ended $ended -LogPath $logPath -Note $Reason
}

# Resolve interpreter without installing anything.
$pythonPrefix = @()
if (-not [string]::IsNullOrWhiteSpace($PythonExe)) {
    $pythonCommand = $PythonExe
}
elseif (Test-Path -LiteralPath (Join-Path $RepoPath ".venv\Scripts\python.exe")) {
    $pythonCommand = Join-Path $RepoPath ".venv\Scripts\python.exe"
}
elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonCommand = (Get-Command py).Source
    $pythonPrefix = @("-3")
}
elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonCommand = (Get-Command python).Source
}
else {
    throw "No Python interpreter found. Supply -PythonExe. Runner will not install packages."
}

# Force imports to come from the current in-place worktree even if the chosen interpreter
# has another editable install. Dependencies still resolve from that interpreter environment;
# MechCAD production code resolves from this worktree/src.
$env:PYTHONPATH = Join-Path $worktree "src"
$env:MECHCAD_VERIFICATION_WORKTREE = $worktree

function Invoke-PythonStep {
    param(
        [string]$Name,
        [string[]]$Arguments,
        [string]$Milestone = "GLOBAL",
        [bool]$RequiredForMilestone = $false
    )
    return Invoke-ExternalStep -Name $Name -Exe $pythonCommand -Arguments @($pythonPrefix + $Arguments) -Milestone $Milestone -RequiredForMilestone $RequiredForMilestone
}

# Runtime resolution. No package/runtime installation is performed.
$FreeCADCmd = Resolve-OptionalExecutable -Explicit $FreeCADCmd -EnvironmentValue $env:MECHCAD_FREECADCMD -CommandNames @("FreeCADCmd","freecadcmd") -DefaultPaths @("C:\Program Files\FreeCAD 1.1\bin\FreeCADCmd.exe")
$GmshExe = Resolve-OptionalExecutable -Explicit $GmshExe -EnvironmentValue $env:MECHCAD_GMSH -CommandNames @("gmsh")
$CalculixExe = Resolve-OptionalExecutable -Explicit $CalculixExe -EnvironmentValue $env:MECHCAD_CCX -CommandNames @("ccx")

if (-not [string]::IsNullOrWhiteSpace($FreeCADCmd)) { $env:MECHCAD_FREECADCMD = $FreeCADCmd }
if (-not [string]::IsNullOrWhiteSpace($GmshExe)) { $env:MECHCAD_GMSH = $GmshExe }
if (-not [string]::IsNullOrWhiteSpace($CalculixExe)) { $env:MECHCAD_CCX = $CalculixExe }

$freecadReady = [bool](-not [string]::IsNullOrWhiteSpace($FreeCADCmd) -and (Test-Path -LiteralPath $FreeCADCmd))
$gmshReady = [bool](-not [string]::IsNullOrWhiteSpace($GmshExe) -and (Test-Path -LiteralPath $GmshExe))
$ccxReady = [bool](-not [string]::IsNullOrWhiteSpace($CalculixExe) -and (Test-Path -LiteralPath $CalculixExe))
$structuralReady = [bool]($freecadReady -and $gmshReady -and $ccxReady)

@(
    "python_command=$pythonCommand"
    "python_prefix=$($pythonPrefix -join ' ')"
    "pythonpath=$env:PYTHONPATH"
    "verification_worktree=$env:MECHCAD_VERIFICATION_WORKTREE"
    "freecadcmd=$FreeCADCmd"
    "freecadcmd_exists=$freecadReady"
    "gmsh=$GmshExe"
    "gmsh_exists=$gmshReady"
    "calculix_ccx=$CalculixExe"
    "calculix_ccx_exists=$ccxReady"
    "structural_live_ready=$structuralReady"
    "opencode_live_opt_in=$($env:MECHCAD_OPENCODE_LIVE)"
) | Out-File -Encoding utf8 (Join-Path $meta "runtime_inventory.txt")

# Evidence-local response files keep command lines deterministic and avoid Windows limits.

function Resolve-TestSelectors {
    param([string[]]$Selectors)
    $resolved = @()
    foreach ($selector in $Selectors) {
        if ($selector -match "[\*\?]") {
            $matches = Get-ChildItem -Path (Join-Path $worktree $selector) -File -ErrorAction SilentlyContinue
            foreach ($m in $matches) {
                $relative = $m.FullName.Substring($worktree.Length)
                $relative = $relative.TrimStart([char[]]"\/")
                $relative = $relative.Replace("\","/")
                $resolved += $relative
            }
        }
        else {
            $pathOnly = ($selector -split "::",2)[0]
            if (-not (Test-Path -LiteralPath (Join-Path $worktree $pathOnly))) {
                throw "Required test selector does not exist in worktree: $selector"
            }
            $resolved += $selector.Replace("\","/")
        }
    }
    return @($resolved | Sort-Object -Unique)
}

function Read-JUnitCounts {
    param([string]$XmlPath)
    $counts = [ordered]@{tests=0; failures=0; errors=0; skipped=0}
    if (-not (Test-Path -LiteralPath $XmlPath)) { return $counts }
    try {
        [xml]$doc = Get-Content -LiteralPath $XmlPath -Raw
        $suites = @()
        if ($null -ne $doc.testsuites -and $null -ne $doc.testsuites.testsuite) {
            $suites = @($doc.testsuites.testsuite)
        }
        elseif ($null -ne $doc.testsuite) {
            $suites = @($doc.testsuite)
        }
        foreach ($suite in $suites) {
            if ($null -ne $suite.tests) { $counts.tests += [int]$suite.tests }
            if ($null -ne $suite.failures) { $counts.failures += [int]$suite.failures }
            if ($null -ne $suite.errors) { $counts.errors += [int]$suite.errors }
            if ($null -ne $suite.skipped) { $counts.skipped += [int]$suite.skipped }
        }
    }
    catch {
        # A malformed/missing JUnit is handled by the caller as an execution failure/incomplete record.
    }
    return $counts
}

function Invoke-PytestStage {
    param(
        [string]$Name,
        [string]$Milestone,
        [string[]]$Selectors,
        [bool]$RequiredForMilestone = $true,
        [bool]$RequireZeroSkips = $true,
        [string[]]$ExtraArgs = @()
    )
    if ($OnlyStages.Count -gt 0 -and $OnlyStages -notcontains $Name) {
        Add-NotRunStage -Name $Name -Milestone $Milestone -Reason "Stage omitted by -OnlyStages focused execution filter." -RequiredForMilestone $RequiredForMilestone
        return 0
    }
    $logPath = Join-Path $logs ("{0}.log" -f $Name)
    $xmlPath = Join-Path $meta ("{0}.xml" -f $Name)
    $responseName = "$Name.txt"
    $responseSelector = Join-Path $selectorDir $responseName
    $started = Get-Date

    try {
        $resolved = @(Resolve-TestSelectors -Selectors $Selectors)
        if ($resolved.Count -eq 0) { throw "No test files resolved for $Name" }
        $resolved | Out-File -Encoding ascii $responseSelector
    }
    catch {
        $_ | Out-String | Out-File -Encoding utf8 $logPath
        $ended = Get-Date
        Add-Result -Name $Name -Milestone $Milestone -RequiredForMilestone $RequiredForMilestone -Status "BLOCKED" -ExitCode 9002 -Started $started -Ended $ended -LogPath $logPath -Note "runner selector resolution failed before pytest launch"
        return 9002
    }

    $args = @($pythonPrefix + @(
        "-m","pytest","@$responseSelector","-q","--tb=short","-rA","-p","no:randomly",
        "--junitxml=$xmlPath"
    ) + $ExtraArgs)

    "=== $Name ===" | Tee-Object -FilePath $logPath
    "milestone: $Milestone" | Tee-Object -FilePath $logPath -Append
    "required_for_milestone: $RequiredForMilestone" | Tee-Object -FilePath $logPath -Append
    "require_zero_skips: $RequireZeroSkips" | Tee-Object -FilePath $logPath -Append
    "UTC start: $($started.ToUniversalTime().ToString('o'))" | Tee-Object -FilePath $logPath -Append
    "cwd: $worktree" | Tee-Object -FilePath $logPath -Append
    "selectors_file: $responseSelector" | Tee-Object -FilePath $logPath -Append
    "command: $pythonCommand $($args -join ' ')" | Tee-Object -FilePath $logPath -Append

    Push-Location $worktree
    $launchFailed = $false
    $previousErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        & $pythonCommand @args 2>&1 | Tee-Object -FilePath $logPath -Append
        $code = $LASTEXITCODE
    }
    catch {
        $_ | Out-String | Tee-Object -FilePath $logPath -Append
        $code = 9001
        $launchFailed = $true
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
        Pop-Location
    }

    $ended = Get-Date
    $counts = Read-JUnitCounts -XmlPath $xmlPath
    if ($launchFailed) {
        $status = "BLOCKED"
        $code = 9001
        $note = "pytest process could not be launched by the verification runner"
    }
    elseif ($code -ne 0 -and ($counts.failures -gt 0 -or $counts.errors -gt 0)) {
        $status = "FAIL"
        $note = "pytest recorded test failures or errors"
    }
    elseif ($code -ne 0) {
        $status = "BLOCKED"
        $note = "pytest exited nonzero without JUnit failure/error evidence; test execution was incomplete or unavailable"
    }
    elseif (-not (Test-Path -LiteralPath $xmlPath)) {
        $status = "BLOCKED"
        $code = 9003
        $note = "pytest returned zero but JUnit output is missing"
    }
    elseif ($counts.tests -eq 0) {
        $status = "BLOCKED"
        $code = 9004
        $note = "pytest produced no executed test cases"
    }
    elseif ($RequireZeroSkips -and $counts.skipped -gt 0) {
        $status = "BLOCKED"
        $code = 125
        $note = "required milestone stage contains skipped tests; no pass credit"
    }
    else {
        $status = "PASS"
        $note = ""
    }

    "UTC end: $($ended.ToUniversalTime().ToString('o'))" | Tee-Object -FilePath $logPath -Append
    "exit_code: $code" | Tee-Object -FilePath $logPath -Append
    "junit_tests: $($counts.tests)" | Tee-Object -FilePath $logPath -Append
    "junit_failures: $($counts.failures)" | Tee-Object -FilePath $logPath -Append
    "junit_errors: $($counts.errors)" | Tee-Object -FilePath $logPath -Append
    "junit_skipped: $($counts.skipped)" | Tee-Object -FilePath $logPath -Append
    "credited_status: $status" | Tee-Object -FilePath $logPath -Append

    Add-Result -Name $Name -Milestone $Milestone -RequiredForMilestone $RequiredForMilestone -Status $status -ExitCode $code -Started $started -Ended $ended -LogPath $logPath -Note $note -Tests $counts.tests -Failures $counts.failures -Errors $counts.errors -Skipped $counts.skipped
    return $code
}

# ---------- Preflight / static ----------
Invoke-ExternalStep -Name "00_initial_worktree_status" -Exe "git" -Arguments @("-C",$RepoPath,"status","--short","--branch") | Out-Null
Invoke-ExternalStep -Name "01_inplace_worktree_preflight" -Exe "git" -Arguments @("status","--short","--branch") | Out-Null
$pythonVersionCode = Invoke-PythonStep -Name "02_python_version" -Arguments @("--version") | Select-Object -Last 1
if ($pythonVersionCode -ne 0) { throw "Python preflight failed; verification cannot be trusted." }
$pytestVersionCode = Invoke-PythonStep -Name "02_pytest_version" -Arguments @("-m","pytest","--version") | Select-Object -Last 1
if ($pytestVersionCode -ne 0) { throw "pytest preflight failed; runner will not install packages." }
$importOriginCode = Invoke-PythonStep -Name "02_import_origin" -Arguments @(
    "-c",
    "import os,pathlib,mechcad_harness; p=pathlib.Path(mechcad_harness.__file__).resolve(); root=pathlib.Path(os.environ['MECHCAD_VERIFICATION_WORKTREE']).resolve(); print('mechcad_harness=', p); print('worktree=', root); assert p.is_relative_to(root / 'src'), (p, root)"
) | Select-Object -Last 1
if ($importOriginCode -ne 0) { throw "Import-origin check failed; refusing to run against a different source tree." }
Invoke-PythonStep -Name "02_python_packages" -Arguments @(
    "-c",
    "import importlib.metadata as metadata, importlib.util; print('pip_available=' + str(importlib.util.find_spec('pip') is not None)); [print(distribution.metadata.get('Name', 'unknown') + '==' + distribution.version) for distribution in metadata.distributions()]"
) | Out-Null
$runtimeDiscoveryCode = @'
from mechcad_harness.structural.runtime import discover_freecad, discover_gmsh, discover_calculix
for name, discover in (('freecad', discover_freecad), ('gmsh', discover_gmsh), ('calculix', discover_calculix)):
    runtime = discover()
    print(name, 'available=', runtime.available, 'exe=', runtime.executable, 'observed=', runtime.version, 'required=', runtime.identity.library_version)
'@
Invoke-PythonStep -Name "02_pydantic_version" -Arguments @("-c","import pydantic; print(pydantic.__version__)") | Out-Null
Invoke-PythonStep -Name "02_mechcad_runtime_discovery" -Arguments @(
    "-c",
    $runtimeDiscoveryCode
) | Out-Null

if ($freecadReady) { Invoke-ExternalStep -Name "02_freecad_version" -Exe $FreeCADCmd -Arguments @("--version") | Out-Null }
else { Add-BlockedStage -Name "02_freecad_version" -Milestone "GLOBAL" -Reason "FreeCADCmd unavailable; FreeCAD-required milestone live stages cannot receive credit." -RequiredForMilestone $false }
if ($gmshReady) { Invoke-ExternalStep -Name "02_gmsh_version" -Exe $GmshExe -Arguments @("--version") | Out-Null }
else { Add-BlockedStage -Name "02_gmsh_version" -Milestone "GLOBAL" -Reason "Gmsh unavailable; M11 live stage cannot receive credit." -RequiredForMilestone $false }
if ($ccxReady) { Invoke-ExternalStep -Name "02_calculix_version" -Exe $CalculixExe -Arguments @("-v") -AcceptNonzeroOutputPattern '(?im)^\s*This is Version \d+\.\d+' | Out-Null }
else { Add-BlockedStage -Name "02_calculix_version" -Milestone "GLOBAL" -Reason "CalculiX/ccx unavailable; M11 live stage cannot receive credit." -RequiredForMilestone $false }

Invoke-PythonStep -Name "03_static_compileall" -Arguments @("-m","compileall","-q","src/mechcad_harness","tests") | Out-Null
Invoke-ExternalStep -Name "04_static_git_diff_check" -Exe "git" -Arguments @("diff","--check") | Out-Null
Invoke-ExternalStep -Name "04_static_git_cached_diff_check" -Exe "git" -Arguments @("diff","--cached","--check") | Out-Null

# ---------- M0 -> M6: foundational current-HEAD regressions ----------
Invoke-PytestStage -Name "10_m0_foundation" -Milestone "M0" -Selectors @(
    "tests/unit/test_ids.py",
    "tests/unit/test_models.py",
    "tests/unit/test_core_canonical_serialization.py"
) | Out-Null

Invoke-PytestStage -Name "11_m1_state_foundation" -Milestone "M1" -Selectors @(
    "tests/unit/test_state_foundation.py"
) | Out-Null

Invoke-PytestStage -Name "12_m2_changes" -Milestone "M2" -Selectors @(
    "tests/unit/test_changes.py"
) | Out-Null

Invoke-PytestStage -Name "13_m3_dependency_evidence" -Milestone "M3" -Selectors @(
    "tests/unit/test_dependency.py",
    "tests/unit/test_core_currentness.py"
) | Out-Null

Invoke-PytestStage -Name "14_m4_runs" -Milestone "M4" -Selectors @(
    "tests/unit/test_runs.py"
) | Out-Null

Invoke-PytestStage -Name "15_m5_tools" -Milestone "M5" -Selectors @(
    "tests/unit/test_tools.py"
) | Out-Null

# M5.5A/B/C current capability descendants are credited under the top-level M5 summary.
Invoke-PytestStage -Name "16_m5_5_providers_artifacts_sections" -Milestone "M5" -Selectors @(
    "tests/unit/test_artifacts.py",
    "tests/unit/test_backends.py",
    "tests/unit/test_gear_backend.py",
    "tests/unit/test_gear_cad.py",
    "tests/unit/test_materials.py",
    "tests/unit/test_sections.py",
    "tests/unit/test_section_*.py",
    "tests/unit/test_spur_engineering.py"
) | Out-Null

# M6A/M6B current descendants: agent gateway, mediated tools, transmission, requests/resolution.
Invoke-PytestStage -Name "17_m6_agents_transmission_constraints" -Milestone "M6" -Selectors @(
    "tests/unit/test_agent_*.py",
    "tests/unit/test_agents_*.py",
    "tests/unit/test_opencode_adapter.py",
    "tests/unit/test_opencode_gateway.py",
    "tests/unit/test_transmission_agent.py",
    "tests/unit/test_constraint_requests.py",
    "tests/unit/test_constraint_resolution.py",
    "tests/unit/test_constraint_resolution_admission.py",
    "tests/integration/test_constraint_resolution_canonical_admission.py"
) | Out-Null

if ($env:MECHCAD_OPENCODE_LIVE -eq "1") {
    Invoke-PytestStage -Name "17b_m6_opencode_live_optional" -Milestone "M6" -RequiredForMilestone $false -RequireZeroSkips $true -Selectors @(
        "tests/integration/test_opencode_live.py",
        "tests/integration/test_opencode_gateway_live.py",
        "tests/integration/test_transmission_agent_live.py",
        "tests/integration/test_transmission_constraint_discovery_live.py",
        "tests/integration/test_transmission_roundtrip_live.py"
    ) | Out-Null
}
else {
    Add-NotRunStage -Name "17b_m6_opencode_live_optional" -Milestone "M6" -Reason "MECHCAD_OPENCODE_LIVE is not 1. Historical M6 closure did not retain an M6-wide live acceptance; current OpenCode live probe is recorded as optional rather than silently skipped."
}

# ---------- M7: generic CAD/assembly/exact geometry + reference adapters ----------
Invoke-PytestStage -Name "18_m7_cad_assembly_kinematics_unit" -Milestone "M7" -Selectors @(
    "tests/unit/test_cad_*.py",
    "tests/unit/test_freecad_*.py",
    "tests/unit/test_assembly_integrity.py",
    "tests/unit/test_kinematic_sweep.py",
    "tests/unit/test_transient_assembly_analysis.py",
    "tests/unit/test_transient_freecad_measurement.py",
    "tests/unit/test_m7*.py",
    "tests/unit/test_yagi_kinematic_reference.py",
    "tests/unit/test_azimuth_mount_plate.py",
    "tests/unit/test_through_slot_operation.py"
) | Out-Null

if ($freecadReady) {
    Invoke-PytestStage -Name "18b_m7_live_freecad" -Milestone "M7" -RequireZeroSkips $true -Selectors @(
        "tests/integration/test_cad_program_live.py",
        "tests/integration/test_cad_analysis_live.py",
        "tests/integration/test_cad_assembly_live.py",
        "tests/integration/test_freecad_backend_live.py",
        "tests/integration/test_m7*_live.py",
        "tests/integration/test_azimuth_mount_plate_live.py",
        "tests/integration/test_through_slot_freecad_live.py"
    ) | Out-Null
}
else {
    Add-BlockedStage -Name "18b_m7_live_freecad" -Milestone "M7" -Reason "M7 includes retained live FreeCAD evidence; FreeCADCmd is unavailable."
}

# ---------- M8: production composition / CAD compilation / trusted bridge ----------
Invoke-PytestStage -Name "19_m8_production_composition" -Milestone "M8" -Selectors @(
    "tests/unit/test_production_application.py",
    "tests/unit/test_cad_compilation.py",
    "tests/unit/test_imported_component.py",
    "tests/unit/test_imported_component_trust.py",
    "tests/integration/test_imported_assembly_bridge.py",
    "tests/integration/test_m8*.py"
) | Out-Null

# ---------- M9: required real-FreeCAD system acceptance boundaries ----------
if ($freecadReady) {
    Invoke-PytestStage -Name "20_m9_live_system" -Milestone "M9" -RequireZeroSkips $true -Selectors @(
        "tests/integration/test_m9_1_freecad_runtime_live.py",
        "tests/integration/test_m9_2_real_trusted_imported_artifact.py",
        "tests/integration/test_m9_3_live_mixed_assembly_exact_kinematic.py",
        "tests/integration/test_m9_4_trusted_analysis_backend_provenance.py"
    ) | Out-Null
}
else {
    Add-BlockedStage -Name "20_m9_live_system" -Milestone "M9" -Reason "M9 accepted closure is LIVE_VERIFIED and requires real FreeCAD."
}

# ---------- M10: deterministic FK + real-FreeCAD collision/continuous proof ----------
Invoke-PytestStage -Name "21_m10_motion_unit" -Milestone "M10" -Selectors @(
    "tests/test_m10_1_continuous_proof.py",
    "tests/unit/test_multi_joint_*.py",
    "tests/unit/test_m10_semantic_projections.py"
) | Out-Null
if ($freecadReady) {
    Invoke-PytestStage -Name "21b_m10_live_system" -Milestone "M10" -RequireZeroSkips $true -Selectors @(
        "tests/integration/test_m10_1_live_continuous_proof.py",
        "tests/integration/test_m10_3_live_multi_joint_collision.py",
        "tests/integration/test_m10_3_provenance.py",
        "tests/integration/test_m10_4_live_continuous_multi_joint_path.py",
        "tests/integration/test_m10_4_provenance.py",
        "tests/integration/test_m10_5_system_acceptance.py"
    ) | Out-Null
}
else {
    Add-BlockedStage -Name "21b_m10_live_system" -Milestone "M10" -Reason "M10 accepted closure is LIVE_VERIFIED and requires real FreeCAD exact geometry."
}

# ---------- M11: structural units + mandatory FreeCAD/Gmsh/CalculiX live chain ----------
Invoke-PytestStage -Name "22_m11_structural_unit" -Milestone "M11" -Selectors @(
    "tests/unit/test_structural_*.py",
    "tests/unit/test_m11_handoff_v2.py"
) | Out-Null
if ($structuralReady) {
    Invoke-PytestStage -Name "22b_m11_live_structural" -Milestone "M11" -RequireZeroSkips $true -Selectors @(
        "tests/integration/test_m11_3_live_structural.py",
        "tests/integration/test_m11_4_live_structural.py",
        "tests/integration/test_m11_5_live_structural.py"
    ) | Out-Null
}
else {
    $missing = @()
    if (-not $freecadReady) { $missing += "FreeCAD" }
    if (-not $gmshReady) { $missing += "Gmsh" }
    if (-not $ccxReady) { $missing += "CalculiX" }
    Add-BlockedStage -Name "22b_m11_live_structural" -Milestone "M11" -Reason ("M11 live acceptance requires FreeCAD + Gmsh + CalculiX. Missing: " + ($missing -join ", "))
}

# ---------- M12: candidate authority/realization/promotion and live E2E ----------
Invoke-PytestStage -Name "23_m12_candidate_promotion_unit" -Milestone "M12" -Selectors @(
    "tests/unit/test_m12_*.py"
) | Out-Null
if ($freecadReady) {
    Invoke-PytestStage -Name "23b_m12_live_production" -Milestone "M12" -RequireZeroSkips $true -Selectors @(
        "tests/integration/test_m12_*.py"
    ) | Out-Null
}
else {
    Add-BlockedStage -Name "23b_m12_live_production" -Milestone "M12" -Reason "M12-6 accepted end-to-end closure requires real FreeCAD."
}

# ---------- M13: interface/generated-part/multi-joint/promotion full stack ----------
Invoke-PytestStage -Name "24_m13_unit" -Milestone "M13" -Selectors @(
    "tests/unit/test_m13_*.py",
    "tests/unit/test_semantic_m13_projections.py"
) | Out-Null
if ($freecadReady) {
    Invoke-PytestStage -Name "24b_m13_live_integration" -Milestone "M13" -RequireZeroSkips $true -Selectors @(
        "tests/integration/test_m13_*.py"
    ) | Out-Null
}
else {
    Add-BlockedStage -Name "24b_m13_live_integration" -Milestone "M13" -Reason "M13 accepted terminal baseline contains real-FreeCAD live boundaries."
}

# ---------- Post-M13 current HEAD: accepted deterministic STEP content identity Epic ----------
# This closes the retained finding that P8.2 broad regression was not rerun on exact final provenance bytes.
Invoke-PytestStage -Name "25_post_m13_p8_2_required_units" -Milestone "POST_M13" -RequireZeroSkips $true -Selectors @(
    "tests/unit/test_m12_*.py",
    "tests/unit/test_m13_*.py",
    "tests/unit/test_candidate_*.py",
    "tests/unit/test_canonical_*.py",
    "tests/unit/test_multi_joint_*.py",
    "tests/unit/test_structural_*.py"
) | Out-Null

Invoke-PytestStage -Name "25b_post_m13_p8_2_required_integrations" -Milestone "POST_M13" -RequireZeroSkips $true -Selectors @(
    "tests/integration/test_m12_candidate_cad_m10_production.py",
    "tests/integration/test_m12_promotion_production.py"
) -ExtraArgs @("-k","not live") | Out-Null

# Ensure fresh semantic MINI replay workspace for dedicated T-P8.3 evidence.
$tp83GeneratedRoot = Join-Path $worktree ".tmp-live-m12\tp8_3_mini_replay"
if (($OnlyStages.Count -eq 0 -or $OnlyStages -contains "26_post_m13_tp8_3_live_step_identity") -and (Test-Path -LiteralPath $tp83GeneratedRoot)) {
    Remove-Item -LiteralPath $tp83GeneratedRoot -Recurse -Force
}
if ($freecadReady) {
    Invoke-PytestStage -Name "26_post_m13_tp8_3_live_step_identity" -Milestone "POST_M13" -RequireZeroSkips $true -Selectors @(
        "tests/integration/test_step_content_identity_live.py"
    ) | Out-Null
}
else {
    Add-BlockedStage -Name "26_post_m13_tp8_3_live_step_identity" -Milestone "POST_M13" -Reason "T-P8.3 live verification requires real FreeCAD."
}

# ---------- Whole-tree final regression ----------
# Optional skips are retained here rather than converted to failure, because the all-M
# milestone stages above already fail closed on required milestone skips/live runtimes.
Invoke-PytestStage -Name "27_full_repository_pytest" -Milestone "GLOBAL" -RequiredForMilestone $false -RequireZeroSkips $false -Selectors @(
    "tests"
) -ExtraArgs @("--durations=50") | Out-Null

Invoke-ExternalStep -Name "28_final_status" -Exe "git" -Arguments @("status","--short","--branch") | Out-Null


# ---------- In-place mutation check ----------
# Verification is allowed to write only its own evidence tree and the dedicated fresh T-P8.3 workspace.
& git -C $RepoPath status --porcelain=v2 --branch --untracked-files=all 2>&1 | Out-File -Encoding utf8 (Join-Path $meta "final_git_status.txt")
& git -C $RepoPath diff --binary HEAD 2>&1 | Out-File -Encoding utf8 (Join-Path $meta "final_worktree_diff.patch")

# The tracked diff must be unchanged by tests. Existing tracked changes are preserved and verified as-is.
# Compare tracked diff bytes captured before/after rather than requiring a clean worktree.
$initialDiffHash = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $meta "initial_worktree_diff.patch")).Hash
$finalDiffHash = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $meta "final_worktree_diff.patch")).Hash
if ($initialDiffHash -ne $finalDiffHash) {
    $started = Get-Date
    $logPath = Join-Path $logs "28b_unexpected_tracked_mutation.log"
    @(
        "FAIL: tracked worktree diff changed during verification"
        "initial_diff_sha256=$initialDiffHash"
        "final_diff_sha256=$finalDiffHash"
        "No reset/clean was performed. Inspect initial/final patches in meta/."
    ) | Out-File -Encoding utf8 $logPath
    $ended = Get-Date
    Add-Result -Name "28b_unexpected_tracked_mutation" -Milestone "GLOBAL" -RequiredForMilestone $false -Status "FAIL" -ExitCode 126 -Started $started -Ended $ended -LogPath $logPath -Note "verification mutated tracked repository bytes"
}
else {
    $started = Get-Date
    $logPath = Join-Path $logs "28b_tracked_state_preserved.log"
    "PASS: tracked worktree diff SHA-256 remained $initialDiffHash" | Out-File -Encoding utf8 $logPath
    $ended = Get-Date
    Add-Result -Name "28b_tracked_state_preserved" -Milestone "GLOBAL" -RequiredForMilestone $false -Status "PASS" -ExitCode 0 -Started $started -Ended $ended -LogPath $logPath -Note "existing tracked changes preserved byte-for-byte"
}

# ---------- Milestone aggregation ----------
$milestoneIds = @("M0","M1","M2","M3","M4","M5","M6","M7","M8","M9","M10","M11","M12","M13","POST_M13")
$milestoneSummary = @()
foreach ($milestone in $milestoneIds) {
    $rows = @($script:Results | Where-Object { $_.milestone -eq $milestone -and $_.required_for_milestone -eq $true })
    if ($rows.Count -eq 0) {
        $status = "NOT_RUN"
    }
    elseif (@($rows | Where-Object { $_.status -eq "FAIL" }).Count -gt 0) {
        $status = "FAIL"
    }
    elseif (@($rows | Where-Object { $_.status -eq "BLOCKED" }).Count -gt 0) {
        $status = "BLOCKED"
    }
    elseif (@($rows | Where-Object { $_.status -ne "PASS" }).Count -gt 0) {
        $status = "INCOMPLETE"
    }
    else {
        $status = "PASS"
    }
    $milestoneSummary += [pscustomobject]@{
        milestone = $milestone
        status = $status
        required_stage_count = $rows.Count
        passed = @($rows | Where-Object { $_.status -eq "PASS" }).Count
        failed = @($rows | Where-Object { $_.status -eq "FAIL" }).Count
        blocked = @($rows | Where-Object { $_.status -eq "BLOCKED" }).Count
    }
}
$milestoneSummary | Export-Csv -NoTypeInformation -Encoding utf8 (Join-Path $meta "milestone_summary.csv")
$milestoneSummary | ConvertTo-Json -Depth 4 | Out-File -Encoding utf8 (Join-Path $meta "milestone_summary.json")
$script:Results | ConvertTo-Json -Depth 4 | Out-File -Encoding utf8 (Join-Path $meta "results.json")

$failedStages = @($script:Results | Where-Object { $_.status -eq "FAIL" }).Count
$blockedStages = @($script:Results | Where-Object { $_.status -eq "BLOCKED" }).Count
$passedStages = @($script:Results | Where-Object { $_.status -eq "PASS" }).Count
$failedMilestones = @($milestoneSummary | Where-Object { $_.status -eq "FAIL" }).Count
$blockedMilestones = @($milestoneSummary | Where-Object { $_.status -eq "BLOCKED" }).Count
$passedMilestones = @($milestoneSummary | Where-Object { $_.status -eq "PASS" }).Count
$allM0M13Pass = @($milestoneSummary | Where-Object { $_.milestone -match '^M([0-9]|1[0-3])$' -and $_.status -ne "PASS" }).Count -eq 0
$postM13Pass = @($milestoneSummary | Where-Object { $_.milestone -eq "POST_M13" -and $_.status -eq "PASS" }).Count -eq 1

@(
    "run_root=$runRoot"
    "worktree=$worktree"
    "verified_head=$worktreeHead"
    "verification_mode=IN_PLACE"
    "tracked_dirty_at_start=$initialTrackedDirty"
    "relevant_untracked_at_start=$($untrackedRelevant.Count)"
    "passed_stages=$passedStages"
    "failed_stages=$failedStages"
    "blocked_stages=$blockedStages"
    "passed_milestones=$passedMilestones"
    "failed_milestones=$failedMilestones"
    "blocked_milestones=$blockedMilestones"
    "all_m0_m13_pass=$allM0M13Pass"
    "post_m13_pass=$postM13Pass"
    "historical_mini_reused=False"
    "full_verification_credit_allowed=$([bool]($allM0M13Pass -and $postM13Pass -and $failedStages -eq 0 -and $blockedStages -eq 0))"
) | Out-File -Encoding utf8 (Join-Path $runRoot "SUMMARY.txt")

Write-Host "In-place verification complete. Evidence root: $runRoot"
Write-Host "M0-M13 all PASS: $allM0M13Pass; POST_M13 PASS: $postM13Pass"
Write-Host "PASS stages: $passedStages; FAIL stages: $failedStages; BLOCKED stages: $blockedStages"

if (-not $allM0M13Pass -or -not $postM13Pass -or $failedStages -gt 0 -or $blockedStages -gt 0) { exit 1 } else { exit 0 }
