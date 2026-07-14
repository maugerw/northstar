
The tasks below are likely to take 2 weeks for the first GMX environment. Efficiency can be obtained through repetition or possibly scripting with the WebLogic Scripting tool (WLST). I will look in to possible use of WLST for configuration export/import.

A local update of Jdeveloper and its supporting JDK on BAU AVDs to work with SOA Suite 14c is likely to be required to adapt SOA and OSB composites.

Depending on what WebLogic and Oracle resources can preconfigure:

# system users

# custom database packages
COMMON_LOGGING_UTIL_PKG

# custom database connections
WAM_XXCUST

# JMS modules and queues
GIS_OSB_JMS_Module
- GIS_FileNotificationJMSQueue

GIS_SAF_JMS_Module
- GIS_ErrorHandlerSAF_SOA
- GIS_ImportedSAF_Destination_SOA
- GIS_RemoteSAF_Context_SOA

GIS_SAF_SOA_JMS_Module
- GIS_SAF_ImportedDestinations_OSB
- RemoteSAF_OSB

GIS_SOA_JMS_Module
- GIS_PublishChangeSetJMSQueue_SOA
- GIS_UpdateJobStatusJMSQueue_SOA

WAMJMSModule
- WAMJMSConnectionFactory
- WAM_CBRM_JMS_Q
- WAM_Chime_JMS_Q
- WAM_EH_JMS_Q
- WAM_HICI_JMS_Q
- WAM_IPS_JMS_Q
- WAM_MX_JMS_Q
- WAM_SerialNum_JMS_Q

# application deployments
SSENXPathFunctions.jar
ErrorHospitalWebApp
SOAScheduler
EO_FtpAdapter

# SOA MDS deployment

# SOA and OSB config plans

# SOA composites
AssetEBSAsync
LocationEBSAsync
PublishEOChangeSetRequestorABCS
PublishErrorHandler
PublishRestrictionsEBS
PublishRestrictionsRequestorABCS
PublishRestrictionsResponseProviderABCS
ServiceAddressAsync
SSENAutoAlertingUtil
UpdateAddressProviderABCS
UpdateAssetProviderABCS
UpdateJobStatusProviderABCS
UpdateLocationProviderABCS

# OSB composites
BatchResubmissionUtil
CreateUpdateChimeAllowedValueCS
CreateUpdateChimeAssetAndSpecCS
CreateUpdateChimeClassCS
CreateUpdateChimeLocationAndSpecCS
CreateUpdateChimePropertyCS
CreateUpdateChimeWorkOrderCS
EnterpriseMetaModel
EOFileNotification
EOPublishChangeSetCS
GenericResponseCS
GetCHIMETokenPS
GIS_MDS_OSB
ManageCBRMMessagePS
ManageChimeMessagePS
ManageIPSMessagePS
ManageSerialNumberCS
ManageServiceNowPS
MessageLoggingUtil
MessageLoggingUtil02
PublishAssetAndSpecCS
PublishChimeClassificationCS
PublishChimeDomainCS
PublishLocationAndSpecCS
PublishMaximoProjectCode
PublishRegionCS
PublishRRPCategoryCS
PublishWorkOrderCS
ResubmissionUtil
SharedObjects
UpdateAssetHICIRiskCS
UpdateMaximoAssetHICIRiskPS
UpdateMaximoMessageIS
UpdateMaximoWorkOrderCS
UpdateMaximoWOSpecsPS
UpdateWOSpecsCS

# ErrorReports and automation (less important on non-PRD)

# ErrorHospital install DB table trim scripts
