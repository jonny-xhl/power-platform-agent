"""
Power Platform Metadata Manager
完整的元数据管理器 - 支持通过YAML定义进行表的CRUD操作

支持功能：
1. 创建表 (create)
2. 修改表 (update/modify)
3. 创建字段 (create_attribute)
4. 修改字段 (update_attribute)
5. 删除字段 (delete_attribute)
6. 创建关系 (create_relationship)
7. 删除关系 (delete_relationship)
8. 字段选项集 - 本地选项集
9. 全局选项集引用 (global_option_set)
"""

import logging
import time
from typing import Any

from ..utils.retry_helper import wait_for_default_components, MetadataPropagationError

logger = logging.getLogger(__name__)


def _safe_get(data: Any, *keys, default=None):
    """
    安全地获取嵌套字典属性

    Args:
        data: 数据对象（可能是 None 或字典）
        *keys: 嵌套键路径
        default: 默认值

    Returns:
        获取到的值或默认值
    """
    if data is None:
        return default
    for key in keys:
        if isinstance(data, dict):
            data = data.get(key)
        else:
            return default
        if data is None:
            return default
    return data if data is not None else default


class MetadataChange:
    """元数据变更项"""

    def __init__(
        self,
        change_type: str,
        target_type: str,
        target_name: str,
        current_value: Any = None,
        desired_value: Any = None,
        metadata_id: str = None
    ):
        self.change_type = change_type  # create, update, delete
        self.target_type = target_type  # entity, attribute, relationship, option_set
        self.target_name = target_name
        self.current_value = current_value
        self.desired_value = desired_value
        self.metadata_id = metadata_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "change_type": self.change_type,
            "target_type": self.target_type,
            "target_name": self.target_name,
            "current_value": self.current_value,
            "desired_value": self.desired_value,
            "metadata_id": self.metadata_id
        }


class MetadataDiff:
    """元数据差异分析结果"""

    def __init__(self, entity_name: str):
        self.entity_name = entity_name
        self.changes: list[MetadataChange] = []

    def add_change(self, change: MetadataChange):
        self.changes.append(change)

    def has_changes(self) -> bool:
        return len(self.changes) > 0

    def get_changes_by_type(self, change_type: str) -> list[MetadataChange]:
        return [c for c in self.changes if c.change_type == change_type]

    def get_changes_by_target(self, target_type: str) -> list[MetadataChange]:
        return [c for c in self.changes if c.target_type == target_type]

    def summary(self) -> dict[str, int]:
        summary = {}
        for change in self.changes:
            key = f"{change.target_type}_{change.change_type}"
            summary[key] = summary.get(key, 0) + 1
        return summary

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_name": self.entity_name,
            "has_changes": self.has_changes(),
            "summary": self.summary(),
            "changes": [c.to_dict() for c in self.changes]
        }


class MetadataManager:
    """
    元数据管理器 - 处理完整的元数据CRUD操作

    工作流程：
    1. 解析YAML定义获取期望状态
    2. 查询Dataverse获取当前状态
    3. 计算差异（diff）
    4. 应用变更（apply）
    """

    def __init__(self, client):
        """
        初始化元数据管理器

        Args:
            client: DataverseClient实例
        """
        self.client = client

    # ==================== 状态查询 ====================

    def get_current_state(self, entity_name: str) -> dict[str, Any]:
        """
        获取实体当前的完整状态

        Args:
            entity_name: 实体名称

        Returns:
            当前状态字典
        """
        logger.info(f"Getting current state for entity: {entity_name}")

        try:
            entity_metadata = self.client.get_entity_metadata(entity_name)
        except Exception:
            # 实体不存在
            logger.info(f"Entity {entity_name} does not exist yet")
            return {
                "entity": None,
                "attributes": {},
                "relationships": {},
                "option_sets": {}
            }

        attributes = self.client.get_attributes(entity_name)
        relationships = self.client.get_relationships(entity_name)

        # 整理属性
        attributes_dict = {}
        for attr in attributes:
            attr_name = attr.get("SchemaName")
            attributes_dict[attr_name] = self._serialize_attribute(attr)

        # 整理关系
        relationships_dict = {}
        for rel in relationships:
            rel_name = rel.get("SchemaName")
            relationships_dict[rel_name] = self._serialize_relationship(rel)

        return {
            "entity": {
                "schema_name": entity_metadata.get("SchemaName"),
                "logical_name": entity_metadata.get("LogicalName"),
                "metadata_id": entity_metadata.get("MetadataId"),
                "ownership_type": entity_metadata.get("OwnershipType"),
                "display_name": _safe_get(entity_metadata, "DisplayName", "UserLocalizedLabel", "Label", default=""),
                "description": _safe_get(entity_metadata, "Description", "UserLocalizedLabel", "Label", default=""),
                "has_activities": entity_metadata.get("HasActivities", False),
                "has_notes": entity_metadata.get("HasNotes", False),
            },
            "attributes": attributes_dict,
            "relationships": relationships_dict,
            "option_sets": {}  # 从属性中提取选项集信息
        }

    def _serialize_attribute(self, attr: dict[str, Any]) -> dict[str, Any]:
        """序列化属性元数据"""
        result = {
            "schema_name": attr.get("SchemaName"),
            "logical_name": attr.get("LogicalName"),
            "metadata_id": attr.get("MetadataId"),
            "type": attr.get("@odata.type", "").split(".")[-1].replace("AttributeMetadata", ""),
            "display_name": _safe_get(attr, "DisplayName", "UserLocalizedLabel", "Label", default=""),
            "description": _safe_get(attr, "Description", "UserLocalizedLabel", "Label", default=""),
            "required_level": _safe_get(attr, "RequiredLevel", "Value"),
            "is_valid_for_create": attr.get("IsValidForCreate", True),
            "is_valid_for_update": attr.get("IsValidForUpdate", True),
        }

        # 类型特定属性
        attr_type = result["type"]

        if attr_type == "String":
            result["max_length"] = attr.get("MaxLength")
        elif attr_type == "Money":
            result["precision"] = attr.get("Precision")
            result["precision_source"] = attr.get("PrecisionSource")
        elif attr_type == "Picklist":
            option_set = attr.get("OptionSet", {})
            result["is_global"] = option_set.get("IsGlobal", False)
            if option_set.get("IsGlobal"):
                result["global_option_set_name"] = option_set.get("Name")
            else:
                result["options"] = [
                    {
                        "value": opt.get("Value"),
                        "label": _safe_get(opt, "Label", "UserLocalizedLabel", "Label", default=""),
                        "color": opt.get("Color")
                    }
                    for opt in option_set.get("Options", [])
                ]
        elif attr_type == "DateTime":
            result["format"] = attr.get("Format")
        elif attr_type == "Memo":
            result["max_length"] = attr.get("MaxLength")
        elif attr_type in ("Lookup", "Customer", "Owner"):
            result["targets"] = attr.get("Targets", [])

        return result

    def _serialize_relationship(self, rel: dict[str, Any]) -> dict[str, Any]:
        """序列化关系元数据"""
        rel_type = rel.get("@odata.type", "")

        result = {
            "schema_name": rel.get("SchemaName"),
            "metadata_id": rel.get("MetadataId"),
            "type": rel_type.split(".")[-1].replace("RelationshipMetadata", ""),
        }

        if "OneToMany" in rel_type:
            result.update({
                "referenced_entity": rel.get("ReferencedEntity"),
                "referencing_entity": rel.get("ReferencingEntity"),
                "referencing_attribute": rel.get("ReferencingAttribute"),
                "cascade_configuration": rel.get("CascadeConfiguration", {})
            })
        elif "ManyToOne" in rel_type:
            result.update({
                "referenced_entity": rel.get("ReferencedEntity"),
                "referencing_entity": rel.get("ReferencingEntity"),
            })
        elif "ManyToMany" in rel_type:
            result.update({
                "entity1": rel.get("Entity1"),
                "entity2": rel.get("Entity2"),
                "intersect_entity": rel.get("IntersectEntity")
            })

        return result

    # ==================== 差异分析 ====================

    def compute_diff(
        self,
        entity_name: str,
        desired_metadata: dict[str, Any]
    ) -> MetadataDiff:
        """
        计算当前状态与期望状态的差异

        Args:
            entity_name: 实体名称
            desired_metadata: 期望的元数据（从YAML解析）

        Returns:
            MetadataDiff对象
        """
        diff = MetadataDiff(entity_name)

        current_state = self.get_current_state(entity_name)

        # 1. 检查实体是否存在
        if current_state["entity"] is None:
            # 实体不存在 - 需要创建
            diff.add_change(MetadataChange(
                change_type="create",
                target_type="entity",
                target_name=entity_name,
                desired_value=desired_metadata.get("schema", {})
            ))
            return diff  # 新实体，后续组件会在实体创建后处理

        # 2. 比较属性
        desired_attributes = desired_metadata.get("attributes", [])
        desired_lookup_attrs = {
            (attr.get("schema_name") or attr.get("name")): attr
            for attr in desired_metadata.get("lookup_attributes", [])
        }

        # 当前属性字典
        current_attrs = current_state["attributes"]

        # 合并普通属性和lookup属性
        all_desired_attrs = list(desired_attributes)
        for lookup_attr in desired_metadata.get("lookup_attributes", []):
            # 检查是否已在attributes中
            lookup_name = lookup_attr.get("schema_name") or lookup_attr.get("name")
            if not any((a.get("schema_name") or a.get("name")) == lookup_name for a in desired_attributes):
                all_desired_attrs.append(lookup_attr)

        for desired_attr in all_desired_attrs:
            attr_name = desired_attr.get("schema_name") or desired_attr.get("name")
            current_attr = current_attrs.get(attr_name)

            if current_attr is None:
                # 属性不存在 - 需要创建
                diff.add_change(MetadataChange(
                    change_type="create",
                    target_type="attribute",
                    target_name=attr_name,
                    desired_value=desired_attr
                ))
            else:
                # 属性存在 - 检查是否需要更新
                attr_diff = self._compare_attribute(current_attr, desired_attr)
                if attr_diff:
                    diff.add_change(MetadataChange(
                        change_type="update",
                        target_type="attribute",
                        target_name=attr_name,
                        current_value=current_attr,
                        desired_value=desired_attr,
                        metadata_id=current_attr.get("metadata_id")
                    ))

        # 检查需要删除的属性（可选，通常不自动删除）
        # desired_attr_names = {a.get("schema_name") or a.get("name") for a in all_desired_attrs}
        # for attr_name, current_attr in current_attrs.items():
        #     if attr_name not in desired_attr_names and not current_attr.get("is_system", True):
        #         diff.add_change(MetadataChange(
        #             change_type="delete",
        #             target_type="attribute",
        #             target_name=attr_name,
        #             current_value=current_attr,
        #             metadata_id=current_attr.get("metadata_id")
        #         ))

        # 3. 比较关系
        desired_relationships = desired_metadata.get("relationships", [])

        # 对于关系，我们从referenced实体的角度创建OneToMany关系
        # 所以需要检查referenced实体上的关系
        for desired_rel in desired_relationships:
            rel_name = desired_rel.get("schema_name") or desired_rel.get("name")
            related_entity = desired_rel.get("related_entity")  # noqa: F841

            # 查找当前关系中是否存在
            current_rel = None
            for rel_name_key, rel_value in current_state["relationships"].items():
                if rel_name_key == rel_name:
                    current_rel = rel_value
                    break

            if current_rel is None:
                # 关系不存在 - 需要创建
                # 获取对应的lookup属性定义
                lookup_attr_name = desired_rel.get("referencing_attribute")
                lookup_attr_def = desired_lookup_attrs.get(lookup_attr_name)

                diff.add_change(MetadataChange(
                    change_type="create",
                    target_type="relationship",
                    target_name=rel_name,
                    desired_value={
                        **desired_rel,
                        "lookup_attribute": lookup_attr_def
                    }
                ))
            else:
                # 关系存在 - 检查是否需要更新（级联配置等）
                rel_diff = self._compare_relationship(current_rel, desired_rel)
                if rel_diff:
                    diff.add_change(MetadataChange(
                        change_type="update",
                        target_type="relationship",
                        target_name=rel_name,
                        current_value=current_rel,
                        desired_value=desired_rel,
                        metadata_id=current_rel.get("metadata_id")
                    ))

        return diff

    def _compare_attribute(
        self,
        current: dict[str, Any],
        desired: dict[str, Any]
    ) -> bool:
        """比较属性是否需要更新"""
        # 比较关键字段
        if current.get("display_name") != desired.get("display_name"):
            return True

        if current.get("description") != desired.get("description"):
            return True

        # 比较required level
        desired_required = "ApplicationRequired" if desired.get("required") else "None"
        if current.get("required_level") != desired_required:
            return True

        # 类型特定比较
        attr_type = desired.get("type")

        if attr_type == "String":
            if current.get("max_length") != desired.get("max_length"):
                return True

        elif attr_type == "Picklist":
            # 比较选项集
            desired_global = desired.get("global_option_set")
            current_global = current.get("global_option_set_name")

            # 检查是否都使用全局选项集或都使用本地选项集
            if (desired_global and not current_global) or (not desired_global and current_global):
                return True  # 一个使用全局，一个使用本地

            if desired_global:
                # 都使用全局选项集 - 比较名称
                if desired_global != current_global:
                    return True
            else:
                # 都使用本地选项集 - 比较选项值
                current_options = {opt.get("value"): opt for opt in current.get("options", [])}
                for desired_opt in desired.get("options", []):
                    current_opt = current_options.get(desired_opt.get("value"))
                    if not current_opt or current_opt.get("label") != desired_opt.get("label"):
                        return True

        return False

    def _compare_relationship(
        self,
        current: dict[str, Any],
        desired: dict[str, Any]
    ) -> bool:
        """比较关系是否需要更新

        Note: Dataverse WebAPI 不支持 PUT 更新已有关系。
        检测到的差异仅用于 plan_changes() 展示，
        apply_diff() 中会跳过实际更新操作。
        """
        # 比较级联配置
        current_cascade = current.get("cascade_configuration", {})
        desired_cascade = {
            "Assign": self._map_cascade_type(desired.get("cascade_assign", "Cascade")),
            "Delete": self._map_cascade_type(desired.get("cascade_delete", "RemoveLink")),
            "Merge": self._map_cascade_type(desired.get("cascade_merge", "NoCascade")),
            "Reparent": self._map_cascade_type(desired.get("cascade_reparent", "Cascade")),
            "Share": self._map_cascade_type(desired.get("cascade_share", "Cascade")),
            "Unshare": self._map_cascade_type(desired.get("cascade_unshare", "Cascade"))
        }

        for key, desired_value in desired_cascade.items():
            if current_cascade.get(key) != desired_value:
                return True

        return False

    def _map_cascade_type(self, yaml_type: str) -> str:
        """映射YAML级联类型到Dataverse值"""
        mapping = {
            "Cascade": "Active",
            "NoCascade": "NoCascade",
            "RemoveLink": "RemoveLink",
            "Restrict": "Restrict"
        }
        return mapping.get(yaml_type, "Active")

    # ==================== 应用变更 ====================

    def apply_diff(
        self,
        diff: MetadataDiff,
        entity_metadata: dict[str, Any],
        options: dict[str, Any] = None
    ) -> dict[str, Any]:
        """
        应用差异到Dataverse

        Args:
            diff: MetadataDiff对象
            entity_metadata: 完整的实体元数据（用于创建实体）
            options: 应用选项

        Returns:
            应用结果
        """
        options = options or {}
        results = {
            "success": True,
            "entity": diff.entity_name,
            "applied": [],
            "failed": [],
            "summary": {}
        }

        # 按顺序处理变更
        # 1. 创建实体（如果需要）
        entity_changes = diff.get_changes_by_type("entity")
        for change in entity_changes:
            if change.change_type == "create":
                result = self._create_entity(entity_metadata)
                results["applied"].append(result)
                if not result.get("success"):
                    results["success"] = False
                    results["failed"].append(result)
                    return results  # 实体创建失败，停止处理

        # 获取实体metadata_id（用于后续操作）
        try:
            entity_info = self.client.get_entity_metadata(diff.entity_name)
            entity_metadata_id = entity_info.get("MetadataId")  # noqa: F841
        except Exception:
            entity_metadata_id = None  # noqa: F841

        # 2. 创建/更新属性（排除Lookup，Lookup通过关系创建）
        attr_changes = [c for c in diff.get_changes_by_target("attribute")
                        if c.desired_value.get("type") not in ("Lookup", "Customer", "Owner")]

        for change in attr_changes:
            try:
                if change.change_type == "create":
                    result = self._create_attribute(diff.entity_name, change.desired_value)
                elif change.change_type == "update":
                    result = self._update_attribute(
                        diff.entity_name,
                        change.metadata_id,
                        change.desired_value
                    )
                else:
                    result = {"success": False, "message": f"Unsupported change type: {change.change_type}"}

                results["applied"].append(result)
                if result.get("success"):
                    results["summary"][f"attribute_{change.change_type}"] = \
                        results["summary"].get(f"attribute_{change.change_type}", 0) + 1
                else:
                    results["failed"].append(result)
            except Exception as e:
                results["failed"].append({
                    "target": change.target_name,
                    "type": change.target_type,
                    "action": change.change_type,
                    "error": str(e)
                })

        # 3. 创建/更新关系（包含Lookup属性的Deep Insert）
        rel_changes = diff.get_changes_by_target("relationship")

        for change in rel_changes:
            try:
                if change.change_type == "create":
                    result = self._create_relationship_with_lookup(
                        diff.entity_name,
                        change.desired_value
                    )
                elif change.change_type == "update":
                    # Dataverse WebAPI 不支持 PUT 更新已有关系（405 Method Not Allowed）
                    # 跳过关系更新，标记为 skipped
                    logger.warning(
                        f"Skipping relationship update for '{change.target_name}': "
                        f"Dataverse does not support updating existing relationships via API. "
                        f"To change cascade config, delete and recreate the relationship manually."
                    )
                    result = {
                        "success": True,
                        "type": "relationship",
                        "action": "update",
                        "name": change.target_name,
                        "skipped": True,
                        "message": (
                            "Relationship update skipped - "
                            "Dataverse does not support PUT on existing relationships"
                        )
                    }
                else:
                    result = {"success": False, "message": f"Unsupported change type: {change.change_type}"}

                results["applied"].append(result)
                if result.get("success") and not result.get("skipped"):
                    results["summary"][f"relationship_{change.change_type}"] = \
                        results["summary"].get(f"relationship_{change.change_type}", 0) + 1
                elif result.get("skipped"):
                    results["summary"]["relationship_skipped"] = \
                        results["summary"].get("relationship_skipped", 0) + 1
                else:
                    results["failed"].append(result)
            except Exception as e:
                results["failed"].append({
                    "target": change.target_name,
                    "type": change.target_type,
                    "action": change.change_type,
                    "error": str(e)
                })

        return results

    def _create_entity(self, metadata: dict[str, Any]) -> dict[str, Any]:
        """
        创建实体

        创建后会等待 Dataverse 自动生成的默认组件（表单、视图）可用。
        这避免了后续操作因元数据传播延时而失败。
        """
        schema_name = metadata.get("schema", {}).get("schema_name")
        try:
            logger.info(f"Creating entity: {schema_name}")
            result = self.client.create_entity(metadata)

            # 等待 Dataverse 自动创建的默认组件可用
            # Dataverse 创建表后会自动创建：
            # - 默认主表单 (Main Form, type=2)
            # - 默认快速创建表单 (Quick Create Form, type=6)
            # - 默认视图 (Active View, Quick Find View)
            self._wait_for_default_components(schema_name)

            return {
                "success": True,
                "type": "entity",
                "action": "create",
                "schema_name": schema_name,
                "result": result
            }
        except Exception as e:
            return {
                "success": False,
                "type": "entity",
                "action": "create",
                "schema_name": schema_name,
                "error": str(e)
            }

    def _wait_for_default_components(self, entity_name: str, timeout: float = 45.0) -> None:
        """
        等待 Dataverse 自动创建的默认组件可用

        Args:
            entity_name: 实体名称
            timeout: 超时时间（秒）
        """
        logger.info(f"Waiting for default components of entity '{entity_name}' to be available...")

        # 定义检查函数
        def check_main_form(_: str, form_type: int) -> dict[str, Any]:
            forms = self.client.get_forms(entity_name, form_type=form_type)
            if not forms:
                raise ValueError(f"No form with type {form_type} found")
            return forms[0]

        def check_view(_: str, __: str) -> dict[str, Any]:
            # 检查 Active Views (query_type=0)
            views = self.client.get_views(entity_name, query_type=0)
            if not views:
                raise ValueError("No active views found")
            return views[0]

        # 等待默认主表单 (type=2)
        try:
            wait_for_default_components(
                check_fn=lambda _, __: check_main_form(_, 2),
                entity_name=entity_name,
                component_type="main_form",
                component_name="Main Form",
                timeout=timeout,
                check_interval=3.0
            )
            logger.info(f"Default main form for '{entity_name}' is now available")
        except MetadataPropagationError as e:
            logger.warning(f"Default main form not available after {timeout}s: {e}")
            # 继续执行，因为主表单可能不是必须的

        # 等待默认视图
        try:
            wait_for_default_components(
                check_fn=check_view,
                entity_name=entity_name,
                component_type="view",
                component_name="Active View",
                timeout=timeout,
                check_interval=3.0
            )
            logger.info(f"Default views for '{entity_name}' are now available")
        except MetadataPropagationError as e:
            logger.warning(f"Default views not available after {timeout}s: {e}")
            # 继续执行

        # 额外等待一下，确保所有元数据完全传播
        time.sleep(2)
        logger.info(f"Default components for '{entity_name}' are ready")

    def _create_attribute(self, entity_name: str, attr_def: dict[str, Any]) -> dict[str, Any]:
        """创建属性"""
        try:
            attr_type = attr_def.get("type")
            attr_metadata = self.client._convert_attribute_metadata(attr_def, attr_type)
            result = self.client.create_attribute(entity_name, attr_metadata)
            return {
                "success": True,
                "type": "attribute",
                "action": "create",
                "name": attr_def.get("schema_name") or attr_def.get("name"),
                "result": result
            }
        except Exception as e:
            return {
                "success": False,
                "type": "attribute",
                "action": "create",
                "name": attr_def.get("schema_name") or attr_def.get("name"),
                "error": str(e)
            }

    def _update_attribute(
        self,
        entity_name: str,
        metadata_id: str,
        attr_def: dict[str, Any]
    ) -> dict[str, Any]:
        """更新属性"""
        try:
            # 构建更新元数据（只包含可更新的字段）
            attr_type = attr_def.get("type")  # noqa: F841
            update_metadata = {
                "DisplayName": self._create_localized_label(attr_def.get("display_name", "")),
                "Description": self._create_localized_label(attr_def.get("description", "")),
                "RequiredLevel": {
                    "Value": "ApplicationRequired" if attr_def.get("required") else "None"
                }
            }

            # 调用更新API
            entity_metadata = self.client.get_entity_metadata(entity_name)
            entity_metadata_id = entity_metadata.get("MetadataId")

            url = self.client.get_api_url(
                f"EntityDefinitions({entity_metadata_id})/Attributes({metadata_id})"
            )

            response = self.client.session.put(url, json=update_metadata)
            response.raise_for_status()

            return {
                "success": True,
                "type": "attribute",
                "action": "update",
                "name": attr_def.get("schema_name") or attr_def.get("name")
            }
        except Exception as e:
            return {
                "success": False,
                "type": "attribute",
                "action": "update",
                "name": attr_def.get("schema_name") or attr_def.get("name"),
                "error": str(e)
            }

    def _create_relationship_with_lookup(
        self,
        entity_name: str,
        rel_def: dict[str, Any]
    ) -> dict[str, Any]:
        """创建关系（包含Lookup的Deep Insert）"""
        try:
            related_entity = rel_def.get("related_entity")  # noqa: F841
            lookup_attr = rel_def.get("lookup_attribute")

            result = self.client.create_relationship(
                entity_name,
                rel_def,
                lookup_attr
            )

            return {
                "success": True,
                "type": "relationship",
                "action": "create",
                "name": rel_def.get("schema_name") or rel_def.get("name"),
                "result": result
            }
        except Exception as e:
            return {
                "success": False,
                "type": "relationship",
                "action": "create",
                "name": rel_def.get("schema_name") or rel_def.get("name"),
                "error": str(e)
            }

    def _update_relationship(
        self,
        entity_name: str,
        metadata_id: str,
        rel_def: dict[str, Any]
    ) -> dict[str, Any]:
        """更新关系的级联配置"""
        try:
            # 关系更新需要从referenced实体端操作
            # 对于ManyToOne关系，实际上是更新OneToMany关系
            related_entity = rel_def.get("related_entity")

            # 构建级联配置
            cascade_map = {
                "Cascade": "Active",
                "NoCascade": "NoCascade",
                "RemoveLink": "RemoveLink",
                "Restrict": "Restrict"
            }

            update_metadata = {
                "CascadeConfiguration": {
                    "Assign": cascade_map.get(rel_def.get("cascade_assign", "Cascade")),
                    "Delete": cascade_map.get(rel_def.get("cascade_delete", "RemoveLink")),
                    "Merge": cascade_map.get(rel_def.get("cascade_merge", "NoCascade")),
                    "Reparent": cascade_map.get(rel_def.get("cascade_reparent", "Cascade")),
                    "Share": cascade_map.get(rel_def.get("cascade_share", "Cascade")),
                    "Unshare": cascade_map.get(rel_def.get("cascade_unshare", "Cascade"))
                }
            }

            # 获取referenced实体的metadata_id
            ref_entity_metadata = self.client.get_entity_metadata(related_entity)
            ref_entity_metadata_id = ref_entity_metadata.get("MetadataId")

            url = self.client.get_api_url(
                f"EntityDefinitions({ref_entity_metadata_id})/OneToManyRelationships({metadata_id})"
            )

            response = self.client.session.put(url, json=update_metadata)
            response.raise_for_status()

            return {
                "success": True,
                "type": "relationship",
                "action": "update",
                "name": rel_def.get("schema_name") or rel_def.get("name")
            }
        except Exception as e:
            return {
                "success": False,
                "type": "relationship",
                "action": "update",
                "name": rel_def.get("schema_name") or rel_def.get("name"),
                "error": str(e)
            }

    def _create_localized_label(self, label: str) -> dict[str, Any]:
        """创建本地化标签"""
        if not label:
            return None
        return {
            "LocalizedLabels": [
                {
                    "Label": label,
                    "LanguageCode": 1033
                },
                {
                    "Label": label,
                    "LanguageCode": 2052
                }
            ]
        }
