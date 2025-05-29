Param (
    [string]$DiskId,
    [string]$SSID,
    [string]$SSIDPassword,
    [string]$CreatePartition = $True ,
    [string]$IgnoreLock = $False,
    [string]$IgnoreFactoryReset = $False,
    [string]$IgnoreBootDrive = $False,
    [string]$SkipDownload = $False,
    [string]$CustomResetUrl,
    [string]$CurrentDirectory  
)
$scriptName = Split-Path -leaf $PSCommandpath
if ( $CurrentDirectory -eq "" ) {
	$CurrentDirectory = Get-Location
}
If (-not ( Test-Path("$($CurrentDirectory)"))) {
	$CurrentDirectory = Get-Location
}
Write-Host "CurrentDirectory  $CurrentDirectory "

$LockFilePath = $CurrentDirectory + "\$($scriptName).lck"

$TimerStartTime = $(get-date)

$ISOFileUrl = 'https://s3.amazonaws.com/deepracer-public/factory-restore/Ubuntu20.04/BIOS-0.0.8/ubuntu-20.04.1-20.11.13_V1-desktop-amd64.iso'
$ISOFileName = $ISOFileUrl.ToString().Substring($ISOFileUrl.ToString().LastIndexOf("/") + 1)

# Use custom reset URL if provided, otherwise use default
if ($CustomResetUrl) {
    $FactoryResetUrl = $CustomResetUrl
    Write-Host "Using custom factory reset URL: $CustomResetUrl"
} else {
    $FactoryResetUrl = 'https://s3.amazonaws.com/deepracer-public/factory-restore/Ubuntu20.04/BIOS-0.0.8/factory_reset.zip'
}
$FactoryResetUrlFileName = $FactoryResetUrl.ToString().Substring($FactoryResetUrl.ToString().LastIndexOf("/") + 1)

$FactoryResetUSBFlashScriptPath = 'usb_flash.sh'
$FactoryResetFolder = [System.IO.Path]::GetFileNameWithoutExtension($FactoryResetUrl.ToString().Substring($FactoryResetUrl.ToString().LastIndexOf("/") + 1))

function Show-Usage {
    Write-Host ""
    Write-Host "Usage: "
    Write-Host ""
    Write-Host "    .\$($scriptName) -DiskId <disk number> [ -SSID <WIFI_SSID> -SSIDPassword <WIFI_PASSWORD>] [-CustomResetUrl <URL>]"
    Write-Host ""
    Write-Host " or if you want to start it in a separate window:"
    Write-Host ""
    Write-Host "    start powershell {.\$($scriptName) -DiskId <disk number> [ -SSID <WIFI_SSID> -SSIDPassword <WIFI_PASSWORD>] [-CustomResetUrl <URL>]}"
    Write-Host ""
    Write-Host "Parameters:"
    Write-Host "    -DiskId <number>           : USB disk number (required)"
    Write-Host "    -SSID <name>              : WiFi network name (optional)"
    Write-Host "    -SSIDPassword <password>  : WiFi password (optional, requires -SSID)"
    Write-Host "    -CustomResetUrl <url>     : Custom factory reset URL (optional)"
    Write-Host "    -CreatePartition <bool>   : Create new partitions (default: True)"
    Write-Host "    -IgnoreLock <bool>        : Ignore lock file (default: False)"
    Write-Host "    -IgnoreFactoryReset <bool>: Skip factory reset setup (default: False)"
    Write-Host "    -IgnoreBootDrive <bool>   : Skip boot drive creation (default: False)"
    Write-Host "    -SkipDownload <bool>      : Skip file downloads (default: False)"
}
function Show-Disk {
    Write-Host ""
    Write-Host "List of available disks:"
    (Get-Disk | Where-Object BusType -eq 'usb')
    Write-Host ""
}
function Show-Exit {
    Param (
        [Parameter(Mandatory=$True )] [int]$code=0    
    )    
    Write-Host ""
    Write-Host "Exiting, press any key to continue..."
    Write-Host ""
    $null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown');
    exit $code
}
Function New-File-Unzip {
    Param (
        [Parameter(Mandatory=$True )] [string]$FileName 
    )
    $TimerStartTimeUnzip = $(get-date)

    # Get the file name without extension as we will use it to check if the Zip was already extracted
    $directory = [System.IO.Path]::GetFileNameWithoutExtension($FileName) 

    # Check if the destination directory exists so we don't need to download
    If ( -not ( Test-Path("$($directory)") ) ) { 
        Write-Host "  Unzip-File - $($directory) folder doesn't exists, extracting..."
        Expand-Archive $FileName -DestinationPath "$($CurrentDirectory)\"
    } else {
        Write-Host "  Unzip-File - $FileName folder already extracted, not extracting..."
    }
    $TimerEapsedTimeUnzip = $(get-date) - $TimerStartTimeUnzip
    $TimerTotalTimeUnzip = "{0:HH:mm:ss}" -f ([datetime]$TimerEapsedTimeUnzip.Ticks)
    Write-Host "  Unzip-File - Elapsed time: $TimerTotalTimeUnzip"    
}
Function New-File-Download {
    Param (
        [Parameter(Mandatory=$True)] [System.Uri]$url
    )
    $TimerStartTimeDownload = $(get-date)

    Write-Host "  Download-File - Processing url : $url"
    $FilePath = "$($CurrentDirectory)\$($url.ToString().Substring($url.ToString().LastIndexOf("/") + 1))"

    # Make sure the destination directory exists
    # System.IO.FileInfo works even if the file/dir doesn't exist, which is better then get-item which requires the file to exist
    # If (! ( Test-Path ([System.IO.FileInfo]$FilePath).DirectoryName ) ) { [void](New-Item ([System.IO.FileInfo]$FilePath).DirectoryName -force -type directory)}

    #see if this file exists
    Write-Host "  Download-File - Checking if $FilePath already exists locally"
    if ( -not (Test-Path $FilePath) ) {
        #use simple download
        Write-Host "  Download-File - File wasn't downloaded, downloading to $FilePath..."
        # [void] (New-Object System.Net.WebClient).DownloadFile($url.ToString(), $FilePath)
        $useBitTransfer = $null -ne (Get-Module -Name BitsTransfer -ListAvailable) -and ($PSVersionTable.PSVersion.Major -le 5)
        if ($useBitTransfer) {
            Write-Host "  Download-File - Using BitTransfer method"
            Start-BitsTransfer -Source $url.ToString() -Destination $FilePath
        } else {
            Invoke-WebRequest -Uri $url.ToString() -OutFile $FilePath
        }
    } else {
        Write-Host "  Download-File - File already downloaded, not donwloading $FilePath..."
    }
    $TimerEapsedTimeDownload = $(get-date) - $TimerStartTimeDownload
    $TimerTotalTimeDownload = "{0:HH:mm:ss}" -f ([datetime]$TimerEapsedTimeDownload.Ticks)
    Write-Host "  Download-File - Elapsed time: $TimerTotalTimeDownload"
}
Function New-Partition-Path{
    Param (
        [Parameter(Mandatory=$True)] [string]$DiskNumber,
        [Parameter(Mandatory=$True)] [string]$PartitionNumber,
        [Parameter(Mandatory=$True)] [string]$AccessPath
    )
    Remove-Partition-Path -DiskNumber $DiskNumber -PartitionNumber $PartitionNumber  -AccessPath $AccessPath        
    
    Write-Host ""
    Write-Host "  New-Partition-Path - Adding new partition path for DiskNumber $DiskNumber PartitionNumber $PartitionNumber AccessPath $AccessPath"
    Write-Host ""
    New-Item -ItemType Directory -Force -Confirm:$False -Path $AccessPath | Out-Null
    Add-PartitionAccessPath -DiskNumber $DiskNumber -PartitionNumber $PartitionNumber -AccessPath $AccessPath
    
}
Function New-Partition-Drive{
    Param (
        [Parameter(Mandatory=$True)] [string]$DiskNumber,
        [Parameter(Mandatory=$True)] [string]$PartitionNumber,
        [Parameter(Mandatory=$True)] [string]$DriveLetter
    )
    Remove-Partition-Path -DiskNumber $DiskNumber -PartitionNumber $PartitionNumber -AccessPath "$($DriveLetter):"
    
    Write-Host ""
    Write-Host "  New-Partition-Drive - Adding new partition drive for DiskNumber $DiskNumber PartitionNumber $PartitionNumber DriveLetter $DriveLetter"    
    Write-Host ""
    Get-Partition -DiskNumber $DiskNumber -PartitionNumber $PartitionNumber | Set-Partition -NewDriveLetter $DriveLetter   
}
Function Remove-Partition-Path{
    Param (
        [Parameter(Mandatory=$True)] [string]$DiskNumber,
        [Parameter(Mandatory=$True)] [string]$PartitionNumber,
        [Parameter(Mandatory=$True)] [string]$AccessPath
    )
    Write-Host ""
    Write-Host "  Remove-Partition-Path - Removing partition path for DiskNumber $DiskNumber PartitionNumber $PartitionNumber AccessPath $AccessPath"    
    Write-Host ""
    if ( (Test-Path $AccessPath) ) {
        Remove-PartitionAccessPath `
            -DiskNumber $DiskNumber `
            -PartitionNumber $PartitionNumber `
            -AccessPath  "$($AccessPath)"
        Remove-Item -Force -Confirm:$False -Path $AccessPath -Recurse
    }
}
Function New-File-Transfer {
    Param (
        [Parameter(Mandatory=$True)] [string]$path_src,
        [Parameter(Mandatory=$True)] [string]$file_src,
        [Parameter(Mandatory=$True)] [string]$path_dst
    )
    $TimerStartTimeTransfer = $(get-date)

    Write-Host "  Transfer-File - Processing source : $path_src/$file_src"

    #see if this file exists
    Write-Host "  Transfer-File - Checking if $path_dst/$file_src already exists"
    if ( -not (Test-Path "$path_dst/$file_src") ) {
        #use simple download
        Write-Host "  Transfer-File - File doesn't exists..."
        # [void] (New-Object System.Net.WebClient).DownloadFile($url.ToString(), $FilePath)
        $useBitTransfer = $null -ne (Get-Module -Name BitsTransfer -ListAvailable) -and ($PSVersionTable.PSVersion.Major -le 5)
        $useBitTransfer = $null
        if ($useBitTransfer) {
            Write-Host "  Transfer-File - Using BitTransfer method"
            Start-BitsTransfer -Source "$path_src/$file_src" -Destination $path_dst
        } else {
            Copy-Item -Path "$path_src/$file_src" -Destination $path_dst -Recurse -Force
        }
    } else {
        Write-Host "  Transfer-File - File already exists, not transfering..."
    }
    $TimerEapsedTimeTransfer = $(get-date) - $TimerStartTimeTransfer
    $TimerTotalTimeTransfer = "{0:HH:mm:ss}" -f ([datetime]$TimerEapsedTimeTransfer.Ticks)
    Write-Host "  Transfer-File - Elapsed time: $TimerTotalTimeTransfer"
}
Function New-Timer {
    $TimerStartTime = $(get-date)
    Write-Host ""
    Write-Host "  -> Timer started: $TimerStartTime"
    Write-Host ""	
}
Function Remove-Timer {
	$TimerStopTime = $(get-date)
    $TimerEapsedTime = $TimerStopTime - $TimerStartTime
    $TimerTotalTime = "{0:HH:mm:ss}" -f ([datetime]$TimerEapsedTime.Ticks)
    Write-Host ""
    Write-Host "  -> Timer stopped: $TimerStopTime - Elapsed time: $TimerTotalTime"
    Write-Host ""
}
Function Set-Lock{
    Param (
        [Parameter(Mandatory=$True)] [string]$DiskId
    )    
    $LockFilePath = $CurrentDirectory + "\$($scriptName).lck.$($DiskId)"

    If ( -not ( Test-Path("$($LockFilePath)") ) ) { 
        Write-Host "  Set-Lock - Lock file doesn't exists, creating..."
        "$($DiskId)" | Out-File -FilePath $LockFilePath
    } else {
        if ($IgnoreLock -eq $True) {
            Write-Host "  Set-Lock - Disk is already in use as per lock file, ignoring lock as per command parameters..."
        } else {
            Write-Host "  Set-Lock - Disk is already in use as per lock file, exiting..."
            Show-Exit 1
        }
    }
}
Function Remove-Lock{
    Param (
        [Parameter(Mandatory=$True)] [string]$DiskId
    )

    Write-Host "  Remove-Lock - Checking lock file content..."

    $LockFilePath = $CurrentDirectory + "\$($scriptName).lck.$($DiskId)"

    If ( Test-Path("$($LockFilePath)") ) { 
        Write-Host "  Remove-Lock - Removing lock file for Disk Id $($DiskId)..."
        Remove-Item "$($LockFilePath)"
    } else {
        Write-Host "  Remove-Lock - Disk Id $($DiskId) lock file doesn't exists. Strange!!!!!"
    }
}

if(-not($DiskId)) { 
    Show-Usage
    Show-Disk
    Show-Exit 1
}

Write-Host ""
Write-Host "Making some initial checks..."
Write-Host ""

$Disk=(Get-Disk | Where-Object BusType -eq 'usb' | Where-Object Number -eq $DiskId | Select-Object Number, @{n="Size";e={$_.Size /1GB}})
$DiskNumber=($Disk).Number

if(-not($DiskNumber)) { 
    Write-Host ""
    Write-Host "Unable to find the provided Disk Number : $($DiskId)"
    Show-Disk
    Show-Exit 1
}
if( $Disk.Size -lt 20 ) { 
    Write-Host ""
    Write-Host "USB Disk is too small. It must be at least 20GB"
    Show-Exit 1
}

Set-Lock $DiskId

if(($DiskNumber.PartitionStyle -eq "RAW")) { 
    Write-Host ""
    Write-Host "Found a RAW partition, need to initialize..."
    Initialize-Disk -Number $DiskNumber -PartitionStyle MBR -Confirm:$False  
}

if($SkipDownload -eq $False) {
	Write-Host ""
	Write-Host "Downloading required files..."
	Write-Host ""

	New-Timer

	New-File-Download -url $ISOFileUrl
	New-File-Download -url $FactoryResetUrl

	Remove-Timer

	Write-Host ""
	Write-Host "Unzipping required files..."
	Write-Host ""

	New-File-Unzip -FileName $FactoryResetUrlFileName
}

function Pass-Parameters {
    Param ([hashtable]$NamedParameters)
    return ($NamedParameters.GetEnumerator()|%{"-$($_.Key) `"$($_.Value)`""}) -join " "
}

# Self-elevate the script if required
if (-Not ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] 'Administrator')) {
	if ([int](Get-CimInstance -Class Win32_OperatingSystem | Select-Object -ExpandProperty BuildNumber) -ge 6000) {
		$MyInvocation.BoundParameters["CurrentDirectory"] = $CurrentDirectory
		$CommandLine = "-NoExit -File `"" + $MyInvocation.MyCommand.Path + "`" " + (Pass-Parameters $MyInvocation.BoundParameters) + " " + $MyInvocation.UnboundArguments + " -SkipDownload True "
		Start-Process -FilePath PowerShell.exe -Verb Runas -ArgumentList $CommandLine
		Exit
	}
}

# Remainder of script here


$PartitionNumberBOOT = 1
$PartitionNumberDEEPRACER = 2
$PartitionNumberFLASH = 3

$uuid = [guid]::NewGuid().ToString()

$AccessPathDEEPRACER = $($CurrentDirectory) + "\AP_DEEPRACER-$($uuid)"
$AccessPathFLASH     = $($CurrentDirectory) + "\AP_FLASH-$($uuid)"
$AccessPathBOOT      = $($CurrentDirectory) + "\AP_BOOT-$($uuid)"

if($CreatePartition -eq $True) {
    Write-Host ""
    Write-Host "Clearing the disk and creating new partitions (all data/partitions will be erased)"
    Write-Host ""

    New-Timer

    Set-Disk   -Number $($DiskNumber) -IsOffline $False
    Clear-Disk -Number $($DiskNumber) -RemoveData -RemoveOEM -Confirm:$False
	
((@"
select disk $DiskNumber
clean
"@
)|diskpart)  2>$null >$null

	Initialize-Disk -Number $DiskNumber -PartitionStyle "MBR" 2>$null
	Get-Partition -DiskNumber $DiskNumber 2>$null | ForEach-Object {Remove-Partition -DiskNumber $DiskNumber -PartitionNumber $_.PartitionNumber -Confirm:$False 2>$null}
	   
    New-Partition -DiskNumber $DiskNumber -Size 4GB   -IsActive | Format-Volume -FileSystem FAT32 -NewFileSystemLabel "BOOT"      -Confirm:$False 
    New-Partition -DiskNumber $DiskNumber -Size 1GB   -IsActive | Format-Volume -FileSystem FAT32 -NewFileSystemLabel "DEEPRACER" -Confirm:$False 
    New-Partition -DiskNumber $DiskNumber -Size 20GB  -IsActive | Format-Volume -FileSystem EXFAT -NewFileSystemLabel "FLASH"     -Confirm:$False   

    Remove-Timer
}

Write-Host ""
Write-Host "Creating new partition paths"
Write-Host ""

New-Timer

New-Partition-Path -DiskNumber $DiskNumber -PartitionNumber $PartitionNumberBOOT      -AccessPath $AccessPathBOOT
New-Partition-Path -DiskNumber $DiskNumber -PartitionNumber $PartitionNumberDEEPRACER -AccessPath $AccessPathDEEPRACER
New-Partition-Path -DiskNumber $DiskNumber -PartitionNumber $PartitionNumberFLASH     -AccessPath $AccessPathFLASH

Remove-Timer

if($IgnoreFactoryReset -eq $False) {
    Write-Host ""
    Write-Host "Transfering Factory Reset folder to $AccessPathFLASH"
    Write-Host ""
    
    New-Timer
    
    # Copy-Item -Path ".\factory_reset\*" -Destination "$($AccessPathFLASH)" -Recurse -Force -Verbose

    Get-ChildItem "$($CurrentDirectory)\factory_reset\*" | ForEach-Object {
        New-File-Transfer -path_src (Split-Path -Path $_.FullName) -file_src $_.Name -path_dst $AccessPathFLASH
    }

    Remove-Timer

    Write-Host ""
    Write-Host "Adjusting Factory Reset USB Flash script..."
    Write-Host ""
    
    New-Timer
    
    # uncomment `# reboot` on lines 520 & 528 of `usb_flash.sh`
    Copy-Item "$($AccessPathFLASH)/$($FactoryResetUSBFlashScriptPath)" -Destination "$($AccessPathFLASH)/$($FactoryResetUSBFlashScriptPath).bak" -Recurse -Force
    (Get-Content "$($AccessPathFLASH)/$($FactoryResetUSBFlashScriptPath)" -raw ).replace('#reboot', 'reboot') | Set-Content "$($AccessPathFLASH)/$($FactoryResetUSBFlashScriptPath)"
        
    Remove-Timer
}

if(($SSID) -and ($SSIDPassword) ) {
    Write-Host ""
    Write-Host "Adding wifi-creds.txt to the usb flash drive..."
    Write-Host ""
    
    New-Timer

    $WiFiCredsPath = "$($AccessPathDEEPRACER)/wifi-creds.txt"

    "# DeepRacer Wifi Credentials" > $WiFiCredsPath
    "ssid: $($SSID)" >> $WiFiCredsPath
    "password: $($SSIDPassword) " >> $WiFiCredsPath

    Remove-Timer
}

if( $IgnoreBootDrive -eq $False) {
    Write-Host ""
    Write-Host "Create Boot drive..."
    Write-Host ""

    New-Timer

    if((Get-DiskImage -ImagePath "$($CurrentDirectory)\$($ISOFileName)").Attached -eq $False) {
        Write-Host "  $($ISOFileName) is not mounted yet, mounting..."
        $DiskImage  = Mount-DiskImage -ImagePath "$($CurrentDirectory)\$($ISOFileName)"
        $DiskLetter = ($DiskImage | Get-Volume).DriveLetter
    } else {
        Write-Host "  $($ISOFileName) already mounted, reusing..."
        $DiskImage  = (Get-DiskImage -ImagePath "$($CurrentDirectory)\$($ISOFileName)")
        $DiskLetter = ($DiskImage | Get-Volume).DriveLetter
    }
    
    if ($MakeBootable.IsPresent) {
        Set-Location -Path "$($DiskLetter):\boot"
        bootsect.exe /nt60 "$($AccessPathBOOT)"    
    }

    Copy-Item -Path "$($DiskLetter):\*" -Destination "$($AccessPathBOOT)" -Recurse -Force

    $LockFileCount = (Get-ChildItem -Path $CurrentDirectory -filter "$($scriptName).lck.*" | Measure-Object -Property Directory).Count    

    if ($LockFileCount -eq 0) {
        Write-Host "  No more process in progress, unmounting $($ISOFileName)..."
        Dismount-DiskImage -ImagePath "$($CurrentDirectory)\$($ISOFileName)"
    } else {
        Write-Host "  There are processes in progress, cannot unmount $($ISOFileName)..."
        Write-Host "  To unmount, execute the following command:"
        Write-Host ""
        Write-Host "     Dismount-DiskImage -ImagePath $($CurrentDirectory)\$($ISOFileName)"
        Write-Host ""
    }

    Remove-Timer
}

Write-Host ""
Write-Host "Cleaning up..."
Write-Host ""

New-Timer

Remove-Lock $DiskId

Remove-Partition-Path -DiskNumber $DiskNumber -PartitionNumber $PartitionNumberBOOT         -AccessPath  "$($AccessPathBOOT)"
Remove-Partition-Path -DiskNumber $DiskNumber -PartitionNumber $PartitionNumberDEEPRACER    -AccessPath  "$($AccessPathDEEPRACER)"
Remove-Partition-Path -DiskNumber $DiskNumber -PartitionNumber $PartitionNumberFLASH        -AccessPath  "$($AccessPathFLASH)"

Remove-Timer

Show-Exit 0