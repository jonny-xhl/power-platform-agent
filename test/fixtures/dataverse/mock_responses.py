"""
Power Platform Agent - Mock Dataverse API Responses
模拟Dataverse API响应数据
"""

from typing import Any, Dict, List, Optional


# =============================================================================
# 通用响应
# =============================================================================

def success_response(data: Any) -> Dict[str, Any]:
    """成功响应"""
    return {
        "status": "success",
        "data": data,
    }


def error_response(
    code: str,
    message: str,
    inner_error: Optional[Dict] = None,
) -> Dict[str, Any]:
    """错误响应"""
    response = {
        "error": {
            "code": code,
            "message": message,
        }
    }
    if inner_error:
        response["error"]["innerError"] = inner_error
    return response


# =============================================================================
# 实体响应
# =============================================================================

def account_response(
    account_id: str,
    name: str,
    account_number: Optional[str] = None,
) -> Dict[str, Any]:
    """账户实体响应"""
    return {
        "@odata.context": "https://org.crm.dynamics.com/api/data/v9.2/$metadata#accounts/$entity",
        "@odata.etag": f'W/"{account_id}"',
        "accountid": account_id,
        "name": name,
        "accountnumber": account_number or f"ACC-{account_id[:8].upper()}",
        "statecode": 0,
        "statuscode": 1,
        "customertypecode": 1,
    }


def contact_response(
    contact_id: str,
    first_name: str,
    last_name: str,
    email: Optional[str] = None,
) -> Dict[str, Any]:
    """联系人实体响应"""
    return {
        "@odata.context": "https://org.crm.dynamics.com/api/data/v9.2/$metadata#contacts/$entity",
        "@odata.etag": f'W/"{contact_id}"',
        "contactid": contact_id,
        "firstname": first_name,
        "lastname": last_name,
        "emailaddress1": email or f"{first_name.lower()}.{last_name.lower()}@example.com",
        "statecode": 0,
        "statuscode": 1,
    }


def solution_response(
    solution_id: str,
    unique_name: str,
    version: str = "1.0.0.0",
    friendly_name: Optional[str] = None,
    is_managed: bool = False,
) -> Dict[str, Any]:
    """解决方案实体响应"""
    return {
        "@odata.context": "https://org.crm.dynamics.com/api/data/v9.2/$metadata#solutions/$entity",
        "@odata.etag": f'W/"{solution_id}"',
        "solutionid": solution_id,
        "uniquename": unique_name,
        "friendlyname": friendly_name or unique_name,
        "version": version,
        "ismanaged": is_managed,
        "publisherid": {
            "publisherid": "fd140aaf-4df4-11db-8d3a-001124aebc3b",
            "friendlyname": "DefaultPublisher",
        },
    }


# =============================================================================
# 查询响应
# =============================================================================

def query_response(entities: List[Dict], next_link: Optional[str] = None) -> Dict[str, Any]:
    """查询响应"""
    response = {
        "@odata.context": "https://org.crm.dynamics.com/api/data/v9.2/$metadata#accounts",
        "value": entities,
    }
    if next_link:
        response["@odata.nextLink"] = next_link
    return response


def empty_query_response() -> Dict[str, Any]:
    """空查询响应"""
    return {
        "@odata.context": "https://org.crm.dynamics.com/api/data/v9.2/$metadata#accounts",
        "value": [],
    }


# =============================================================================
# 元数据响应
# =============================================================================

def entity_metadata_response(
    logical_name: str,
    display_name: str,
    schema_name: Optional[str] = None,
    entity_set_name: Optional[str] = None,
) -> Dict[str, Any]:
    """实体元数据响应"""
    return {
        "MetadataId": f"{logical_name}-metadata-id",
        "LogicalName": logical_name,
        "DisplayName": {
            "UserLocalizedLabel": {
                "Label": display_name,
            },
        },
        "SchemaName": schema_name or logical_name.title().replace("_", ""),
        "EntitySetName": entity_set_name or f"{logical_name}s",
        "IsCustomizable": {
            "Value": True,
        },
        "Attributes": [],
    }


def attribute_metadata_response(
    logical_name: str,
    display_name: str,
    attribute_type: str,
    is_required: bool = False,
) -> Dict[str, Any]:
    """属性元数据响应"""
    return {
        "MetadataId": f"{logical_name}-metadata-id",
        "LogicalName": logical_name,
        "DisplayName": {
            "UserLocalizedLabel": {
                "Label": display_name,
            },
        },
        "AttributeType": attribute_type,
        "IsRequiredLevel": {
            "Value": "SystemRequired" if is_required else "None",
        },
        "IsValidForCreate": True,
        "IsValidForUpdate": True,
    }


# =============================================================================
# 认证响应
# =============================================================================

def whoami_response(
    user_id: str,
    user_name: str,
    organization_id: str,
    business_unit_id: str,
) -> Dict[str, Any]:
    """WhoAmI响应"""
    return {
        "@odata.context": "https://org.crm.dynamics.com/api/data/v9.2/$metadata#Microsoft.Dynamics.CRM.WhoAmIResponse",
        "UserId": user_id,
        "UserName": user_name,
        "OrganizationId": organization_id,
        "BusinessUnitId": business_unit_id,
    }


# =============================================================================
# 错误响应
# =============================================================================

def authentication_failed() -> Dict[str, Any]:
    """认证失败响应"""
    return error_response(
        code="AAsts90048",
        message="The authentication failed",
        inner_error={"code": "AAsts90048"},
    )


def authorization_failed() -> Dict[str, Any]:
    """授权失败响应"""
    return error_response(
        code="0x80040220",
        message="The caller does not have the required privileges",
        inner_error={"code": "0x80040220"},
    )


def entity_not_found(entity_name: str, entity_id: str) -> Dict[str, Any]:
    """实体未找到响应"""
    return error_response(
        code="0x80040217",
        message=f"{entity_name} With Id = {entity_id} Does Not Exist",
        inner_error={"code": "0x80040217"},
    )


def validation_error(field_name: str, message: str) -> Dict[str, Any]:
    """验证错误响应"""
    return error_response(
        code="0x80040203",
        message=f"Validation failed for '{field_name}': {message}",
        inner_error={"code": "0x80040203"},
    )


def throttle_error(retry_after: int = 60) -> Dict[str, Any]:
    """限流错误响应"""
    return error_response(
        code="0x8004f070",
        message="System busy, please try again later",
        inner_error={"code": "0x8004f070"},
    )


# =============================================================================
# 批量操作响应
# =============================================================================

def batch_response(responses: List[Dict], error: bool = False) -> Dict[str, Any]:
    """批量操作响应"""
    return {
        "responses": responses,
        "error": error,
    }


def change_set_response(change_set_id: str) -> Dict[str, Any]:
    """变更集响应"""
    return {
        "changeSetId": change_set_id,
    }


# =============================================================================
# 导入/导出响应
# =============================================================================

def import_response(import_job_id: str, status: str = "Submitted") -> Dict[str, Any]:
    """导入响应"""
    return {
        "importjobid": import_job_id,
        "status": status,
        "progress": 0 if status == "Submitted" else 100,
    }


def export_response(export_job_id: str, status: str = "Submitted") -> Dict[str, Any]:
    """导出响应"""
    return {
        "exportjobid": export_job_id,
        "status": status,
        "progress": 0 if status == "Submitted" else 100,
    }


# =============================================================================
# 预定义数据
# =============================================================================

MOCK_ACCOUNTS = [
    account_response(
        account_id="00000000-0000-0000-0000-000000000001",
        name="Contoso Ltd",
        account_number="ACC001",
    ),
    account_response(
        account_id="00000000-0000-0000-0000-000000000002",
        name="Fabrikam Inc",
        account_number="ACC002",
    ),
    account_response(
        account_id="00000000-0000-0000-0000-000000000003",
        name="Adventure Works",
        account_number="ACC003",
    ),
]

MOCK_CONTACTS = [
    contact_response(
        contact_id="00000000-0000-0000-0000-000000000010",
        first_name="John",
        last_name="Smith",
        email="john.smith@contoso.com",
    ),
    contact_response(
        contact_id="00000000-0000-0000-0000-000000000011",
        first_name="Jane",
        last_name="Doe",
        email="jane.doe@fabrikam.com",
    ),
]

MOCK_SOLUTIONS = [
    solution_response(
        solution_id="00000000-0000-0000-0000-000000000100",
        unique_name="Active",
        version="9.2.0.0",
        friendly_name="Active Solution",
        is_managed=False,
    ),
    solution_response(
        solution_id="00000000-0000-0000-0000-000000000101",
        unique_name="Default",
        version="1.0.0.0",
        friendly_name="Default Solution",
        is_managed=False,
    ),
]
