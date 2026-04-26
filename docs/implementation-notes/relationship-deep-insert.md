# Relationship and Lookup Field Creation - Deep Insert Pattern

## Summary

Implemented the "Deep Insert" pattern for creating Lookup attributes and ManyToOne relationships in Dataverse. This approach creates both the lookup field and the relationship in a single API call to the `RelationshipDefinitions` endpoint.

## Changes Made

### 1. `framework/utils/dataverse_client.py`

#### Updated `_create_many_to_one_as_one_to_many` method
- Now accepts optional `lookup_attribute` parameter
- Embeds `LookupAttributeMetadata` inside `OneToManyRelationshipMetadata` for deep insert
- Uses proper primary key attribute names for standard entities (accountid, systemuserid, etc.)
- Added localized label support for embedded lookup attributes

#### Updated `create_relationship` method
- Now accepts optional `lookup_attribute` parameter
- Passes lookup attribute to `_create_many_to_one_as_one_to_many` for deep insert

### 2. `framework/agents/metadata_agent.py`

#### Fixed import paths
- Changed `from utils.xxx` to `from framework.utils.xxx`

#### Updated `create_table` method
- Entity is now created WITHOUT lookup attributes in the Attributes array
- Lookup attributes are created later via relationship deep insert
- Relationships now receive corresponding lookup attribute definitions
- Relationship creation uses deep insert pattern

#### Updated auto-generated lookup relationships
- Now also uses deep insert pattern for lookups defined in attributes but without explicit relationships

### 3. `metadata/tables/payment_recognition.yaml`

#### Updated relationship definitions
- Added `account_new_payment_recognition` relationship (following Microsoft naming convention)
- Added `systemuser_new_payment_recognition_handledby` relationship
- Added `systemuser_new_payment_recognition_approvedby` relationship

#### Cleaned up duplicate definitions
- Removed duplicate Lookup attributes from main attributes section
- Kept only the definitions in `lookup_attributes` section

## API Pattern

The deep insert pattern follows this structure:

```json
POST [Organization URI]/api/data/v9.2/RelationshipDefinitions
{
  "@odata.type": "Microsoft.Dynamics.CRM.OneToManyRelationshipMetadata",
  "SchemaName": "account_new_payment_recognition",
  "ReferencedEntity": "account",
  "ReferencingEntity": "new_payment_recognition",
  "ReferencedAttribute": "accountid",
  "ReferencingAttribute": "new_customerid",
  "CascadeConfiguration": {
    "Assign": "Active",
    "Delete": "RemoveLink",
    ...
  },
  "Lookup": {
    "@odata.type": "Microsoft.Dynamics.CRM.LookupAttributeMetadata",
    "SchemaName": "new_customerid",
    "DisplayName": {
      "LocalizedLabels": [...]
    },
    "AttributeType": "Lookup",
    "Targets": ["account"]
  }
}
```

## YAML Structure

### Relationship Definition
```yaml
relationships:
  - name: "account_new_payment_recognition"
    related_entity: "account"
    relationship_type: "ManyToOne"
    display_name: "客户"
    referencing_attribute: "new_customerid"
    cascade_assign: "Cascade"
    cascade_delete: "RemoveLink"
    ...
```

### Lookup Attribute Definition
```yaml
lookup_attributes:
  - name: "new_customerid"
    type: "Lookup"
    display_name: "客户"
    description: "关联的客户"
    required: false
    target: "account"
```

## Key Points

1. **Naming Convention**: Relationship names should follow `ReferencedEntity_ReferencingEntity` pattern
2. **Single Operation**: Deep insert creates both lookup and relationship in one API call
3. **Standard Entities**: Primary key names are mapped automatically (accountid, systemuserid, etc.)
4. **Cascade Configuration**: Properly mapped from YAML names to Dataverse values

## Testing

Run the test script to verify:
```bash
export DATAVERSE_ACCESS_TOKEN="your_token"
python test/test_relationship_creation.py --action create
```

Query the created entity to verify:
```bash
python test/test_relationship_creation.py --action query
```

## References

- [Microsoft Learn: Create and update entity relationships using Web API](https://learn.microsoft.com/en-us/power-apps/developer/data-platform/webapi/create-update-entity-relationships-using-web-api)
- [RelationshipDefinitions Entity](https://learn.microsoft.com/en-us/power-apps/developer/data-platform/reference/entities/relationshipdefinitions)
