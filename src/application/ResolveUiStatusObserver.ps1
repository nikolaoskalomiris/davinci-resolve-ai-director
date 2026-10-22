param(
    [ValidateRange(250, 5000)]
    [int]$IntervalMs = 500
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes

# Directly verified against Resolve Studio 21.1.0.17 UI Automation output:
# left-to-right UiPageSwitcher button order.
$PageByIndex = @(
    'Media',
    'Photo',
    'Cut',
    'Edit',
    'Fusion',
    'Color',
    'Fairlight',
    'Deliver'
)

$cachedPid = $null
$cachedHandle = [IntPtr]::Zero
$cachedRoot = $null
$cachedButtons = @()
$lastSignature = $null
$lastStablePid = $null
$lastStablePage = $null
$lastStableProject = $null
$lastStableMainWindowTitle = $null

function Emit-State {
    param(
        [bool]$Connected,
        [Nullable[int]]$ProcessId,
        [string]$Page,
        [string]$Project,
        [string]$MainWindowTitle,
        [string]$ErrorText
    )

    $payload = [pscustomobject][ordered]@{
        event = 'state'
        connected = $Connected
        pid = $ProcessId
        page = if ([string]::IsNullOrWhiteSpace($Page)) { $null } else { $Page }
        project = if ([string]::IsNullOrWhiteSpace($Project)) { $null } else { $Project }
        main_window_title = if ([string]::IsNullOrWhiteSpace($MainWindowTitle)) { $null } else { $MainWindowTitle }
        error = if ([string]::IsNullOrWhiteSpace($ErrorText)) { $null } else { $ErrorText }
        source = 'windows_uia_page_switcher'
        timestamp = (Get-Date).ToString('o')
    }

    $signature = '{0}|{1}|{2}|{3}|{4}|{5}' -f `
        $payload.connected, $payload.pid, $payload.page, $payload.project, `
        $payload.main_window_title, $payload.error

    if ($signature -ne $script:lastSignature) {
        $script:lastSignature = $signature
        [Console]::Out.WriteLine(($payload | ConvertTo-Json -Compress))
        [Console]::Out.Flush()
    }
}

function Clear-UiCache {
    $script:cachedPid = $null
    $script:cachedHandle = [IntPtr]::Zero
    $script:cachedRoot = $null
    $script:cachedButtons = @()
}

function Clear-StableState {
    $script:lastStablePid = $null
    $script:lastStablePage = $null
    $script:lastStableProject = $null
    $script:lastStableMainWindowTitle = $null
}

function Get-ResolveProcess {
    try {
        return [System.Diagnostics.Process]::GetProcessesByName('Resolve') |
            Sort-Object Id |
            Select-Object -First 1
    } catch {
        return $null
    }
}

function Get-ToggleState {
    param([System.Windows.Automation.AutomationElement]$Element)

    $pattern = $null
    if ($Element.TryGetCurrentPattern(
        [System.Windows.Automation.TogglePattern]::Pattern,
        [ref]$pattern
    )) {
        return [string]$pattern.Current.ToggleState
    }
    return $null
}

function Acquire-PageSwitcher {
    param(
        [System.Diagnostics.Process]$Process,
        [IntPtr]$Handle
    )

    if ($Handle -eq [IntPtr]::Zero) {
        Clear-UiCache
        return $false
    }

    $root = [System.Windows.Automation.AutomationElement]::FromHandle($Handle)
    if (-not $root) {
        Clear-UiCache
        return $false
    }

    $switcherCondition = New-Object System.Windows.Automation.AndCondition(
        (New-Object System.Windows.Automation.PropertyCondition(
            [System.Windows.Automation.AutomationElement]::ClassNameProperty,
            'UiPageSwitcher'
        )),
        (New-Object System.Windows.Automation.PropertyCondition(
            [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
            [System.Windows.Automation.ControlType]::Group
        ))
    )

    $switcher = $root.FindFirst(
        [System.Windows.Automation.TreeScope]::Descendants,
        $switcherCondition
    )
    if (-not $switcher) {
        Clear-UiCache
        return $false
    }

    $buttonCondition = New-Object System.Windows.Automation.AndCondition(
        (New-Object System.Windows.Automation.PropertyCondition(
            [System.Windows.Automation.AutomationElement]::ClassNameProperty,
            'UiIconTextButton'
        )),
        (New-Object System.Windows.Automation.PropertyCondition(
            [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
            [System.Windows.Automation.ControlType]::CheckBox
        ))
    )

    $found = $switcher.FindAll(
        [System.Windows.Automation.TreeScope]::Descendants,
        $buttonCondition
    )

    if ($found.Count -ne 8) {
        # Do not guess if Blackmagic changes the page-switcher contract.
        Clear-UiCache
        return $false
    }

    $buttons = @()
    for ($i = 0; $i -lt $found.Count; $i++) {
        $element = $found.Item($i)
        $rect = $element.Current.BoundingRectangle
        $buttons += [pscustomobject]@{
            X = [double]$rect.X
            Element = $element
        }
    }

    $buttons = @($buttons | Sort-Object X)

    $script:cachedPid = $Process.Id
    $script:cachedHandle = $Handle
    $script:cachedRoot = $root
    $script:cachedButtons = @($buttons | ForEach-Object { $_.Element })
    return $true
}

function Read-ActivePage {
    param(
        [System.Diagnostics.Process]$Process,
        [IntPtr]$Handle
    )

    $needsAcquire = (
        $null -eq $script:cachedPid -or
        $script:cachedPid -ne $Process.Id -or
        $script:cachedHandle -ne $Handle -or
        @($script:cachedButtons).Count -ne 8
    )

    if ($needsAcquire) {
        if (-not (Acquire-PageSwitcher -Process $Process -Handle $Handle)) {
            return $null
        }
    }

    try {
        $onIndexes = @()
        for ($i = 0; $i -lt $script:cachedButtons.Count; $i++) {
            if ((Get-ToggleState -Element $script:cachedButtons[$i]) -eq 'On') {
                $onIndexes += $i
            }
        }

        if ($onIndexes.Count -eq 1) {
            return $PageByIndex[$onIndexes[0]]
        }

        # Ambiguous state: do not guess.
        return $null
    } catch {
        Clear-UiCache
        return $null
    }
}

while ($true) {
    try {
        $proc = Get-ResolveProcess
        if (-not $proc) {
            Clear-UiCache
            Clear-StableState
            Emit-State -Connected $false -ProcessId $null -Page $null -Project $null -MainWindowTitle $null -ErrorText $null
            Start-Sleep -Milliseconds $IntervalMs
            continue
        }

        try { $proc.Refresh() } catch {}
        $pidValue = [int]$proc.Id
        $title = [string]$proc.MainWindowTitle
        $handle = [IntPtr]$proc.MainWindowHandle

        # A new Resolve process is a real session boundary. Never carry page or
        # project telemetry across PIDs.
        if ($null -eq $script:lastStablePid -or $script:lastStablePid -ne $pidValue) {
            Clear-UiCache
            Clear-StableState
            $script:lastStablePid = $pidValue
        }

        if ($title -eq 'Project Manager') {
            # Positive authoritative state: Resolve explicitly moved to Project Manager.
            $script:lastStablePage = 'Project Manager'
            $script:lastStableProject = $null
            $script:lastStableMainWindowTitle = $title
            Clear-UiCache
        }
        elseif ($title -match '^DaVinci Resolve(?: Studio)?\s+-\s+(.+)$') {
            # Positive authoritative project identity from the real Resolve project window.
            $projectName = $Matches[1].Trim()
            if (-not [string]::IsNullOrWhiteSpace($projectName)) {
                $script:lastStableProject = $projectName
            }
            $script:lastStableMainWindowTitle = $title

            # Leaving Project Manager is also authoritative. Do not keep the
            # Project Manager page label while the page switcher is coming alive.
            if ($script:lastStablePage -eq 'Project Manager') {
                $script:lastStablePage = $null
            }

            if ($handle -ne [IntPtr]::Zero) {
                $observedPage = Read-ActivePage -Process $proc -Handle $handle
                if (-not [string]::IsNullOrWhiteSpace($observedPage)) {
                    $script:lastStablePage = $observedPage
                }
                # IMPORTANT: a null UIA page read is transient/ambiguous, not a
                # state transition. Keep the last confirmed page for this PID.
            }
        }
        else {
            # Qt tooltips, menus, dialogs, and other temporary top-level surfaces
            # can momentarily replace Process.MainWindowTitle/MainWindowHandle.
            # They do not change the active Resolve project or page. Preserve the
            # last confirmed state and avoid probing the transient window.
        }

        Emit-State `
            -Connected $true `
            -ProcessId $pidValue `
            -Page $script:lastStablePage `
            -Project $script:lastStableProject `
            -MainWindowTitle $script:lastStableMainWindowTitle `
            -ErrorText $null
    }
    catch {
        # A one-cycle observation fault is not an authoritative state change.
        # Keep the last confirmed Page/Project for the same live Resolve PID.
        Clear-UiCache
        $proc = Get-ResolveProcess
        if ($proc) {
            try { $proc.Refresh() } catch {}
            $pidValue = [int]$proc.Id
            if ($null -eq $script:lastStablePid -or $script:lastStablePid -ne $pidValue) {
                Clear-StableState
                $script:lastStablePid = $pidValue
            }
            Emit-State `
                -Connected $true `
                -ProcessId $pidValue `
                -Page $script:lastStablePage `
                -Project $script:lastStableProject `
                -MainWindowTitle $script:lastStableMainWindowTitle `
                -ErrorText $_.Exception.Message
        }
        else {
            Clear-StableState
            Emit-State -Connected $false -ProcessId $null -Page $null -Project $null -MainWindowTitle $null -ErrorText $_.Exception.Message
        }
    }

    Start-Sleep -Milliseconds $IntervalMs
}
