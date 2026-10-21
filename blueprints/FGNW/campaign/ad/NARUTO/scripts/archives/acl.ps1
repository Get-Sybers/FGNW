Import-Module ActiveDirectory
Set-Location AD:
Function SetAcl($for, $to, $right, $inheritance)
{
    $forSID = New-Object System.Security.Principal.SecurityIdentifier (Get-ADUser $for).SID
    $objOU = ($to).DistinguishedName
    $objAcl = get-acl $objOU
    $adRight =  [System.DirectoryServices.ActiveDirectoryRights] $right
    $type =  [System.Security.AccessControl.AccessControlType] "Allow"
    $inheritanceType = [System.DirectoryServices.ActiveDirectorySecurityInheritance] $inheritance
    $ace = New-Object System.DirectoryServices.ActiveDirectoryAccessRule $forSID,$adRight,$type,$inheritanceType
    $objAcl.AddAccessRule($ace)
    Set-Acl -AclObject $objAcl -path $objOU
}
Function SetAclExtended($for, $to, $right, $extendedRightGUID, $inheritance)
{
    $forSID = New-Object System.Security.Principal.SecurityIdentifier (Get-ADUser $for).SID
    $objOU = ($to).DistinguishedName
    $objAcl = get-acl $objOU
    $adRight =  [System.DirectoryServices.ActiveDirectoryRights] $right
    $type =  [System.Security.AccessControl.AccessControlType] "Allow"
    $inheritanceType = [System.DirectoryServices.ActiveDirectorySecurityInheritance] $inheritance
    $ace = New-Object System.DirectoryServices.ActiveDirectoryAccessRule $forSID,$adRight,$type,$extendedRightGUID,$inheritanceType
    $objAcl.AddAccessRule($ace)
    Set-Acl -AclObject $objAcl -path $objOU
}
SetAcl (Get-ADUser "hiruzen.sarutobi") (Get-ADUser "tsunade") "GenericAll" "None"
SetAcl (Get-ADUser "lord.varys") (Get-ADGroup "Domain Admins") "GenericAll" "None"
SetAcl (Get-ADUser "stannis.baratheon") (Get-ADComputer "kingslanding") "GenericAll" "None"
SetAcl (Get-ADUser "petyer.baelish") (Get-ADGroup "Domain Admins") "WriteProperty" "All"
SetAclExtended (Get-ADUser "shikamaru.nara") (Get-ADGroup "Domain Admins") "Self" "bf9679c0-0de6-11d0-a285-00aa003049e2" "None"
SetAclExtended (Get-ADUser "stannis.baratheon") (Get-ADGroup "Domain Admins") "WriteProperty" "bf9679c0-0de6-11d0-a285-00aa003049e2" "All"
SetAclExtended (Get-ADUser "hiruzen.sarutobi") (Get-ADUser "asuma.sarutobi") "ExtendedRight" "00299570-246d-11d0-a768-00aa006e0529" "None"
SetAcl (Get-ADUser "maester.pycelle") (Get-ADGroup "Domain Admins") "WriteOwner" "None"
SetAcl (Get-ADUser "asuma.sarutobi") (Get-ADUser "tsunade") "GenericWrite" "None"
SetAcl (Get-ADUser "hiruzen.sarutobi") (Get-ADGroup "Small Council") "WriteDacl" "None"
