<#
.SYNOPSIS
  Watchdog that auto-answers SolidWorks' modal "Component documents must be
  saved" dialog by clicking its "Save All" button.

  This 3DEXPERIENCE Makers seat refuses to save an assembly whose component docs
  are modified through any silent API path (ModelDoc2.Save3 silently no-ops;
  Extension.SaveAs throws) -- the ONLY save that persists the references is the
  one that raises the interactive dialog. A headless build therefore launches
  this watchdog just before calling the blocking ModelDoc2.Save(): the Save()
  call blocks on the modal while this process polls for the "Save All" button and
  physically clicks it, so the build needs no human at the keyboard.

  Exit 0 = clicked; exit 1 = button never appeared within the timeout (e.g. the
  doc was clean and Save() returned without prompting -- harmless).

.PARAMETER ButtonName
  The dialog button to click (default "Save All").
.PARAMETER TimeoutSeconds
  How long to keep polling for the button before giving up (default 180).
#>
param(
  [string]$ButtonName = 'Save All',
  [int]$TimeoutSeconds = 180
)

Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Mouse {
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint f, uint x, uint y, uint d, int e);
  public const uint LEFTDOWN = 0x02, LEFTUP = 0x04;
}
"@

$root = [System.Windows.Automation.AutomationElement]::RootElement
$cond = New-Object System.Windows.Automation.PropertyCondition(
  [System.Windows.Automation.AutomationElement]::NameProperty, $ButtonName)

$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
while ((Get-Date) -lt $deadline) {
  $btn = $root.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $cond)
  if ($btn -and $btn.Current.IsEnabled -and -not $btn.Current.IsOffscreen) {
    # Physical click at the button's clickable point -- InvokePattern proved
    # unreliable on this embedded modal, a real mouse click is robust.
    try {
      $pt = $btn.GetClickablePoint()
      [Mouse]::SetCursorPos([int]$pt.X, [int]$pt.Y) | Out-Null
      Start-Sleep -Milliseconds 120
      [Mouse]::mouse_event([Mouse]::LEFTDOWN, 0, 0, 0, 0)
      Start-Sleep -Milliseconds 60
      [Mouse]::mouse_event([Mouse]::LEFTUP, 0, 0, 0, 0)
      Write-Output "clicked '$ButtonName' at $([int]$pt.X),$([int]$pt.Y)"
      exit 0
    } catch {
      # clickable point not yet available (dialog still rendering) -- retry
    }
  }
  Start-Sleep -Milliseconds 750
}
Write-Output "'$ButtonName' button never appeared within ${TimeoutSeconds}s"
exit 1
