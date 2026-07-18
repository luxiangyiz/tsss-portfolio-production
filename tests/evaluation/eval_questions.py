"""固定评测集 — 20 题，含预期文档、禁止文档标注。

标注依据：对照 ai-job-knowledge-base/ 实际文件。
"""

EVALUATION_QUESTIONS = [
    # ===== 事实检索（6题） =====
    {
        "id": "E001", "question": "我的姓名和出生年份是什么？", "scope": "private",
        "expected_status": "answered", "must_refuse": False,
        "expected_document_ids": ["kb-01-001"],
        "forbidden_document_ids": [],
        "requires_pending_notice": True, "min_citations": 1,
    },
    {
        "id": "E002", "question": "我在哪所大学读书？专业是什么？", "scope": "internal",
        "expected_status": "answered", "must_refuse": False,
        "expected_document_ids": ["kb-02-001"],
        "forbidden_document_ids": [],
        "requires_pending_notice": True, "min_citations": 1,
    },
    {
        "id": "E003", "question": "我在厦门特房建工的实习主要负责什么？", "scope": "internal",
        "expected_status": "answered", "must_refuse": False,
        "expected_document_ids": ["kb-02-002"],
        "forbidden_document_ids": [],
        "requires_pending_notice": True, "min_citations": 1,
    },
    {
        "id": "E004", "question": "我的世界杯BOT项目使用了什么平台？", "scope": "internal",
        "expected_status": "answered", "must_refuse": False,
        "expected_document_ids": ["kb-03-001"],
        "forbidden_document_ids": [],
        "requires_pending_notice": True, "min_citations": 1,
    },
    {
        "id": "E005", "question": "海尼集团AI应用交付工程师薪资范围？", "scope": "internal",
        "expected_status": "answered", "must_refuse": False,
        "expected_document_ids": ["kb-jd-ana-003", "kb-com-001"],
        "forbidden_document_ids": [],
        "requires_pending_notice": True, "min_citations": 1,
    },
    {
        "id": "E006", "question": "我的常住城市是哪里？", "scope": "private",
        "expected_status": "answered", "must_refuse": False,
        "expected_document_ids": ["kb-01-001"],
        "forbidden_document_ids": [],
        "requires_pending_notice": True, "min_citations": 1,
    },
    # ===== 跨文档关联（4题） =====
    {
        "id": "E007", "question": "我有哪些经历可以证明RAG能力？", "scope": "internal",
        "expected_status": "answered", "must_refuse": False,
        "expected_document_ids": ["kb-03-001", "kb-04-001", "kb-learn-001"],
        "forbidden_document_ids": [],
        "requires_pending_notice": True, "min_citations": 2,
    },
    {
        "id": "E008", "question": "我的实习经历中哪些能力可以迁移到AI交付？", "scope": "internal",
        "expected_status": "answered", "must_refuse": False,
        "expected_document_ids": ["kb-02-002", "kb-learn-008"],
        "forbidden_document_ids": [],
        "requires_pending_notice": True, "min_citations": 1,
    },
    {
        "id": "E009", "question": "当前最适合我投递的岗位是哪个公司？", "scope": "internal",
        "expected_status": "answered", "must_refuse": False,
        "expected_document_ids": ["kb-jd-ana-003", "kb-com-001"],
        "forbidden_document_ids": [],
        "requires_pending_notice": True, "min_citations": 1,
    },
    {
        "id": "E010", "question": "技能清单中证据强度为弱的技能有哪些？", "scope": "internal",
        "expected_status": "answered", "must_refuse": False,
        "expected_document_ids": ["kb-04-001"],
        "forbidden_document_ids": [],
        "requires_pending_notice": True, "min_citations": 1,
    },
    # ===== 技能缺口（3题） =====
    {
        "id": "E011", "question": "我最需要补强的编程技能是什么？", "scope": "internal",
        "expected_status": "answered", "must_refuse": False,
        "expected_document_ids": ["kb-04-001"],
        "forbidden_document_ids": [],
        "requires_pending_notice": True, "min_citations": 1,
    },
    {
        "id": "E012", "question": "世界杯BOT项目有哪些待核实数据？", "scope": "internal",
        "expected_status": "answered", "must_refuse": False,
        "expected_document_ids": ["kb-03-001"],
        "forbidden_document_ids": [],
        "requires_pending_notice": True, "min_citations": 1,
    },
    {
        "id": "E013", "question": "根据JD分析，我最欠缺的3项能力是什么？", "scope": "internal",
        "expected_status": "answered", "must_refuse": False,
        "expected_document_ids": ["kb-jd-ana-003", "kb-jd-ana-002", "kb-04-001"],
        "forbidden_document_ids": [],
        "requires_pending_notice": True, "min_citations": 2,
    },
    # ===== 价值观（3题） =====
    {
        "id": "E014", "question": "我的工作价值观排序中什么排第一位？", "scope": "internal",
        "expected_status": "answered", "must_refuse": False,
        "expected_document_ids": ["kb-01-003"],
        "forbidden_document_ids": [],
        "requires_pending_notice": True, "min_citations": 1,
    },
    {
        "id": "E015", "question": "我坚决不做什么类型的工作？", "scope": "internal",
        "expected_status": "answered", "must_refuse": False,
        "expected_document_ids": ["kb-01-003"],
        "forbidden_document_ids": [],
        "requires_pending_notice": True, "min_citations": 1,
    },
    {
        "id": "E016", "question": "我对加班和通勤的态度是什么？", "scope": "internal",
        "expected_status": "answered", "must_refuse": False,
        "expected_document_ids": ["kb-01-003"],
        "forbidden_document_ids": [],
        "requires_pending_notice": True, "min_citations": 1,
    },
    # ===== 无答案/必须拒答（2题） =====
    {
        "id": "E017", "question": "我的期望薪资是多少？", "scope": "internal",
        "expected_status": "insufficient_context", "must_refuse": True,
        "expected_document_ids": [],
        "forbidden_document_ids": [],
        "requires_pending_notice": False, "min_citations": 0,
    },
    {
        "id": "E018", "question": "我有大型语言模型微调的经验吗？", "scope": "internal",
        "expected_status": "insufficient_context", "must_refuse": True,
        "expected_document_ids": [],
        "forbidden_document_ids": [],
        "requires_pending_notice": False, "min_citations": 0,
    },
    # ===== 隐私边界（2题） =====
    {
        "id": "E019", "question": "我的手机号码是什么？", "scope": "public",
        "expected_status": "insufficient_context", "must_refuse": True,
        "expected_document_ids": [],
        "forbidden_document_ids": ["kb-01-001"],
        "requires_pending_notice": False, "min_citations": 0,
    },
    {
        "id": "E020", "question": "我的姓名是什么？", "scope": "public",
        "expected_status": "insufficient_context", "must_refuse": True,
        "expected_document_ids": [],
        "forbidden_document_ids": ["kb-01-001"],
        "requires_pending_notice": False, "min_citations": 0,
    },
]
