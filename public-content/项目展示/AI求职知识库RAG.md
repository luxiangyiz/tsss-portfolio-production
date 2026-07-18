---
id: kb-pub-004
title: 个人求职知识库问答系统
category: 网站项目展示
tags: [RAG, LangChain, FastAPI, Qdrant, 通义千问, DeepSeek]
source: project-015本地系统与验收记录
source_type: project_record
created_at: 2026-07-16
updated_at: 2026-07-18
verification_status: verified
privacy_level: public
publish_status: published
ai_generated: true
review_status: approved
related: [kb-pub-003]
notes: 内容仅描述已经在本地完成并验收的能力。
---

# 个人求职知识库问答系统

## 项目目标

构建一个面向个人 AI 求职的知识库问答系统，将教育经历、项目材料、技能证据、岗位资料与求职复盘进行结构化管理，并将审核后的公开内容接入个人网站。系统需要让回答可以追溯到资料来源，在证据不足时明确拒答，同时确保网站公开问答无法访问私人或内部求职内容。

## 当前架构

- FastAPI：提供健康检查、知识库预览、全量与增量入库、检索、问答和公开问答接口。
- LangChain：连接文档分块、向量模型、向量检索与对话模型。
- Qdrant：按 private、internal、public 三类访问范围保存并检索知识分块向量。
- 通义千问 `text-embedding-v4`：生成1536维语义向量。
- DeepSeek `deepseek-v4-flash`：基于检索证据生成回答。
- Manifest V2：按文档和访问范围记录内容、元数据与分块索引状态，用于判断新增、修改、隐私变化和删除。

## 已实现能力

- 完成知识库扫描、Front Matter 校验、Markdown 文档解析和结构化分块。
- 实现全量建库与增量更新，能够处理新增、修改、元数据变化和删除。
- 建立 private、internal、public 三层索引隔离与对应的访问范围路由。
- 实现基于证据的问答、来源引用和证据不足时拒答。
- 提供本地演示页面与自动验证脚本，用于检查预览、建库、搜索、问答和索引状态。
- 完成本地真实模型运行和公开范围隐私验收。
- 将经过审核的公开资料接入个人网站问答入口。

当前项目已经完成本地工程链路和个人网站公开问答接入。下一阶段将继续使用固定测试集验证真实模型的检索召回、拒答质量和回答稳定性；在结果完成复核前，不展示未经验证的准确率指标。
