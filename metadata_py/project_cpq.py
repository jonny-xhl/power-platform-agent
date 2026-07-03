"""CPQ 项目清单（专用）— 只部署 4 张新表，不触碰任何已有表。

用 `workflow deploy --only tables --project metadata_py/project_cpq.py --env dev`：
仅运行 tables 阶段，创建 new_inquiry / new_inquirydetail / new_quote / new_quotedetail 并加入
new_CpqSoln。所有 lookup 指向环境已存在实体，不改任何已有表的字段。
"""

from framework_power import Project, Publisher

PUBLISHER = Publisher(name="new", display_name="PP", prefix="new")

PROJECT = Project(
    main_solution="new_CpqSoln",
    ribbon_solution="new_RibbonSoln",  # 已存在（Phase 9 smoke）；--only forms,views 不跑 ribbon 阶段
    publisher=PUBLISHER,
    version="1.0.0.0",
    tables=["new_inquiry", "new_inquirydetail", "new_quote", "new_quotedetail"],
    forms=["new_inquiry__Main", "new_inquirydetail__Main", "new_quote__Main", "new_quotedetail__Main"],
    views=["new_inquiry__Active", "new_inquirydetail__Active", "new_quote__Active", "new_quotedetail__Active"],
    webresource_files=[
        "js/new_inquiry/new_inquiry.optionset.js",
        "js/new_inquiry/new_inquiry.form.js",
        "js/new_quote/new_quote.optionset.js",
        "js/new_quote/new_quote.form.js",
        "js/new_inquirydetail/new_inquirydetail.form.js",
        "js/new_quotedetail/new_quotedetail.form.js",
    ],
)
