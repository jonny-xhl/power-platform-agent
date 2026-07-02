"""CPQ Active view (refined from auto-created) — framework_power."""

from framework_power import View, QueryType, ViewColumn, ViewOrder, ViewCondition, ViewFilter, ViewLinkEntity

VIEW: View = View(
    name='Active 询价明细s',
    entity='new_inquirydetail',
    primary_id='new_inquirydetailid',
    object_type_code=11078,
    query_type=QueryType.Public,
    description=None,
    is_default=True,
    columns=[
        ViewColumn(
            name='new_name',
            width=300,
            disable_sorting=False,
            hidden=False,
            attrs={
                'name': 'new_name',
                'width': '300'
            }
        ),
        ViewColumn(
            name='createdon',
            width=125,
            disable_sorting=False,
            hidden=False,
            attrs={
                'name': 'createdon',
                'width': '125'
            }
        ),
        ViewColumn(
            name='new_inquiry_id',
            width=125,
            disable_sorting=False,
            hidden=False,
            attrs={}
        ),
        ViewColumn(
            name='new_product_id',
            width=125,
            disable_sorting=False,
            hidden=False,
            attrs={}
        ),
        ViewColumn(
            name='new_qty',
            width=125,
            disable_sorting=False,
            hidden=False,
            attrs={}
        ),
        ViewColumn(
            name='new_requesteddelivery',
            width=125,
            disable_sorting=False,
            hidden=False,
            attrs={}
        )
    ],
    filters=[
        ViewFilter(
            filter_type='and',
            conditions=[
                ViewCondition(
                    attribute='statecode',
                    operator='eq',
                    value='0',
                    values=[],
                    attrs={
                        'attribute': 'statecode',
                        'operator': 'eq',
                        'value': '0'
                    }
                )
            ],
            filters=[],
            attrs={
                'type': 'and'
            }
        )
    ],
    orders=[
        ViewOrder(
            attribute='new_name',
            descending=False,
            attrs={
                'attribute': 'new_name',
                'descending': 'false'
            }
        )
    ],
    link_entities=[],
    extra_attributes=[],
    fetch_attrs={
        'version': '1.0',
        'mapping': 'logical',
        'savedqueryid': '6d9aee85-0789-45a4-954f-029addcd5324'
    },
    grid_attrs={
        'name': 'resultset',
        'jump': 'new_name',
        'select': '1',
        'icon': '1',
        'preview': '1'
    },
    row_attrs={
        'name': 'result'
    }
)
