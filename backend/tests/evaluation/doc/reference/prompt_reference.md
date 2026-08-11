#### Context Correctness (上下文正确性)
该评估器用于量化评估所提供的**上下文（Context）** 的**事实正确性**和**完整性**。
它的核心任务是判断上下文是否既**准确**（其中的每一个事实都能被标准答案或常识支持）又**完整**（包含了标准答案中的所有关键事实）。
##### **Prompt原文**
```text
Evaluate the correctness of the context on a continuous scale from 0 to 1. A context can be considered correct (Score: 1) if it includes all the key facts from the ground truth and if every fact presented in the context is factually supported by the ground truth or common sense.
```
##### **拆解分析**
- **任务指令**：`Evaluate the correctness of the context`，明确对象是“上下文（context）”，属性是“正确性（correctness）”。注意，这里的“正确性”是一个复合概念。
- **输出格式指令**：`on a continuous scale from 0 to 1`，它要求输出一个连续的分数，而不是分类（如好/中/差）或二元判断（是/否）。
- **评分标准的满分定义**：`A context can be considered correct (Score: 1) if...`，要得1分，必须同时满足两个条件，这是一个“AND”逻辑关系
- **完整性（Completeness/Recall）**：`it includes all the key facts from the ground truth`，评估器必须判断Context是否囊括了Ground Truth中的所有**关键信息点**。不能有重大遗漏。
- **准确性（Accuracy/Precision）**：`every fact presented in the context is factually supported by the ground truth or common sense`，评估器必须判断Context中的**每一个陈述**是否真实可靠。其真实性可以由Ground Truth直接支持，或者，即使Ground Truth未明确提及，但符合人类共识（common sense）也可接受。这防止了Context包含错误或虚假信息。
##### 适合场景
- **评估检索系统（如RAG）的输出质量**：这是最核心的应用。评估检索到的文档片段（Context）是否同时具备高准确率和高召回率，这是决定后续生成答案质量的基础。
- **知识库内容质量审核**：自动化检测知识库中的文章是否存在事实性错误或信息缺失。
- **事实核查（Fact-Checking）**：给定一个声称（Context）和一个事实来源（Ground Truth），自动判断该声称的可信度。
- **对比不同检索算法或数据源**：量化比较哪个算法检索到的上下文更正确、更完整。
##### 小结
Context Correctness 评估器评估的并非是最终答案，而是**生成答案所依赖的“材料”的质量**。一个高质量的上下文是生成高质量答案的前提。
1. **不能有错（Correctness）**：不能有标准答案不支持的错误信息（防止幻觉）。
2. **不能缺漏（Completeness）**：不能缺少标准答案中的关键信息（防止信息不足）。



#### Correctness (答案正确性评估器)
Correctness（答案正确性）评估器用于量化评估大语言模型（LLM）生成的答案在事实准确性方面的可靠程度。它的核心使命是判断生成内容（Generation）是否与公认的事实依据（Ground Truth）完全一致，确保答案既**无事实性错误**，也**无关键信息的遗漏**。该评估器严格遵循“以事实为准绳”的原则。
##### **Prompt原文**
```text
Evaluate the correctness of the context on a continuous scale from 0 to 1. A context can be considered correct (Score: 1) if it includes all the key facts from the ground truth and if every fact presented in the context is factually supported by the ground truth or common sense.
```
##### **拆解分析**
- **任务指令**：`Evaluate the correctness of the context`，明确对象是“上下文（context）”，属性是“正确性（correctness）”。注意，这里的“正确性”是一个复合概念。
- **输出格式指令**：`on a continuous scale from 0 to 1`，它要求输出一个连续的分数，而不是分类（如好/中/差）或二元判断（是/否）。
- **评分标准的满分定义**：`A context can be considered correct (Score: 1) if...`，要得1分，必须同时满足两个条件，这是一个“AND”逻辑关系
- **完整性（Completeness/Recall）**：`it includes all the key facts from the ground truth`，评估器必须判断Context是否囊括了Ground Truth中的所有**关键信息点**。不能有重大遗漏。
- **准确性（Accuracy/Precision）**：`every fact presented in the context is factually supported by the ground truth or common sense`，评估器必须判断Context中的**每一个陈述**是否真实可靠。其真实性可以由Ground Truth直接支持，或者，即使Ground Truth未明确提及，但符合人类共识（common sense）也可接受。这防止了Context包含错误或虚假信息。
##### 适合场景
- **闭卷问答与知识性任务评估**：评估模型在回答事实性问题（如历史、科学、产品规格）时的准确性。
- **模型微调后的效果验证**：在用自己的数据微调模型后，使用此评估器检查模型输出是否与预期知识库一致，是否存在幻觉。
- **对比不同模型或提示词**：在多个模型或不同提示词策略之间进行A/B测试，以确定哪个配置能产生最准确的事实输出。
- **构建高质量评估数据集**：人工编写一批问题的标准答案（Ground Truth）后，可用此评估器自动筛选出生成答案质量高的数据条目。
##### 小结
Correctness 评估器是保障LLM输出事实可靠性的核心工具。它通过**完备性，准确性** 和一个**反例示范**，精准地引导LLM执行严格的事实核查。它的判断严重依赖于高质量的Ground Truth，因此通常用于有明确知识库或标准答案的场景。


#### Hallucination（幻觉评估器）
该评估器用于量化大语言模型生成内容中“幻觉”的程度，即模型输出中包含与客观事实、可验证数据或逻辑推理相违背的信息的比例。
评分范围为0到1，0表示完全无幻觉（内容准确可靠），1表示完全幻觉（内容虚构、误导或不合逻辑）。
##### **Prompt原文**
```text
Evaluate the degree of hallucination in the generation on a continuous scale from 0 to 1. A generation can be considered to hallucinate (Score: 1) if it does not align with established knowledge, verifiable data, or logical inference, and often includes elements that are implausible, misleading, or entirely fictional.
```
##### **拆解分析**
- **任务指令**：`Evaluate the degree of hallucination in the generation`，明确评估对象是"生成内容（generation）"，评估属性是"幻觉程度（degree of hallucination）"。这是一个**负面**属性的量化评估。
- **输出格式指令**：`on a continuous scale from 0 to 1`，它要求输出一个连续的分数，而不是分类（如好/中/差）或二元判断（是/否）。
- **评分标准的满分（严重幻觉）定义：`A generation can be considered to hallucinate (Score: 1) if...`**，这里定义了得1分（即完全幻觉）的条件，包含两个层面的判断：
- **负面验证（什么不是）**: `does not align with established knowledge, verifiable data, or logical inference` - 指出了判断幻觉的三个依据：1) **既定知识**（普遍认可的事实）；2) **可验证数据**（具体、可查证的信息）；3) **逻辑推理**（基于已知前提的合理推论）。生成内容若与这三者任一不符，则存在幻觉风险。
- **正面描述（什么是）**: `and often includes elements that are implausible, misleading, or entirely fictional` - 具体描述了幻觉的三种常见表现形式：1) **implausible**（不合常理的）；2) **misleading**（具有误导性的）；3) **entirely fictional**（完全虚构的）。
##### 适合场景
- 检测模型在问答、摘要、报告生成等任务中是否“编造事实”
- 评估模型在医疗、法律、科技等高风险领域的可靠性
- 对比不同模型或提示词策略的幻觉控制能力
- 用于RAG系统中验证检索结果是否被模型扭曲
##### 小结
hallucination 评估器是保障大模型输出可信度的核心工具，尤其在专业或敏感场景中不可或缺。它不依赖主观感受，而是通过事实核查与逻辑分析进行量化打分，帮助开发者识别并优化模型的可靠性缺陷。使用时需结合领域知识库或权威信源，确保评估客观公正。


#### Helpfulness（有用性评估器）
该评估器用于衡量模型生成内容对用户查询的“实际帮助程度”，评分范围从0到1。
高分（接近1）表示内容不仅准确、相关，还能以清晰、友好、吸引人的方式有效解决或推进用户问题。
低分（接近0）表示内容无关、误导、态度不佳或结构混乱，无法为用户提供实质帮助。
##### **Prompt原文:**
```text
Evaluate the helpfulness of the generation on a continuous scale from 0 to 1. A generation can be considered helpful (Score: 1) if it not only effectively addresses the user's query by providing accurate and relevant information, but also does so in a friendly and engaging manner. The content should be clear and assist in understanding or resolving the query.
```
##### **拆解分析:**
- **任务指令**：`Evaluate the helpfulness of the generation`**，明确评估对象是"生成内容（generation）"，评估属性是"帮助性（helpfulness）"。这是一个综合性的正面属性评估。
- **输出格式指令**：`on a continuous scale from 0 to 1`，它要求输出一个连续的分数，而不是分类（如好/中/差）或二元判断（是/否）。
- **评分标准的满分定义**：`A generation can be considered helpful (Score: 1) if...`，这里定义了得1分（即完全有帮助）需要同时满足的多个条件：
- **核心功能维度（Effectiveness）**: `effectively addresses the user's query` - 必须有效解决用户的查询，这是帮助性的基础。
- **内容质量维度（Quality）**: `providing accurate and relevant information` - 提供的信息必须准确且相关，这是有效性的具体保障。
- **表达风格维度（Manner）**: `friendly and engaging manner` - 回答方式需要友好且吸引人，这是用户体验的提升。
- **清晰度维度（Clarity）**: `clear` - 内容表述必须清晰易懂。
- **实用价值维度（Utility）**: `assist in understanding or resolving the query` - 必须真正有助于用户理解或解决问题，这是帮助性的最终体现。
- `not only... but also...` 的句式强调了这些维度需要**同时满足**，是一个综合性的评判标准。
##### 适合场景
- 用户支持、客服对话系统评估
- 教育、科普类内容生成质量检测
- 对比不同模型或提示词在“用户体验”维度的表现
- 优化模型输出风格（如从机械到亲和）
##### 小结
helpfulness 评估器关注的是模型输出对用户的“实际价值交付”，不仅看“说了什么”，**更看“怎么说”和“有没有用”**。它强调以用户为中心的沟通效果，是提升AI产品体验和用户满意度的关键指标。尤其在面向大众或非专业用户的场景中，友好、清晰、准确三者缺一不可。


#### Relevance（相关性评估器）
该评估器用于衡量模型生成内容与用户查询主题的“聚焦程度”，评分范围从0到1。
高分（接近1）表示内容紧密围绕问题核心，无冗余、无跑题，所提供的信息直接有助于理解或回答该特定问题。
低分（接近0）表示内容偏离主题、夹杂无关信息或过度延伸，导致信息噪音干扰用户获取关键答案。
##### **Prompt原文:**
```text
Evaluate the relevance of the generation on a continuous scale from 0 to 1. A generation can be considered relevant (Score: 1) if it enhances or clarifies the response, adding value to the user's comprehension of the topic in question. Relevance is determined by the extent to which the provided information addresses the specific question asked, staying focused on the subject without straying into unrelated areas or providing extraneous details.
```
##### **拆解分析**
- **任务指令**：`Evaluate the relevance of the generation`，明确评估对象是"生成内容（generation）"，评估属性是"相关性（relevance）"。这是一个基础但关键的属性评估。  
- **输出格式指令**：`on a continuous scale from 0 to 1`，它要求输出一个连续的分数，而不是分类（如好/中/差）或二元判断（是/否）。  
- **评分标准的满分定义**：`A generation can be considered relevant (Score: 1) if...`，定义了得1分需要满足的条件：  
- **价值增值标准**: `enhances or clarifies the response, adding value to the user's comprehension` - 生成内容必须能够增强或澄清回答，为用户的理解增添价值。这表明相关性不仅仅是"提及"，而是要有实质性的信息贡献。  
- **具体准则:** `Relevance is determined by the extent to which...` - 从操作层面给出了更详细的指引：  
- **核心准则**: `addresses the specific question asked` - 信息必须针对所提的具体问题。这是相关性的根本。  
- **负面排除准则**: `staying focused on the subject without straying into unrelated areas or providing extraneous details` - 必须保持主题聚焦，不偏离到无关领域或提供无关细节。这明确了什么是不相关。  
##### 适合场景
- 问答系统、搜索引擎摘要、知识库回复的质量控制
- 评估模型在复杂或多轮对话中是否保持话题聚焦
- 检测RAG系统是否因检索内容混杂导致输出偏离
- 优化提示词工程，避免模型“自由发挥”或“过度解释”
##### 小结
relevance 评估器是确保LLM输出“言之有物、不跑题”的核心工具，在信息过载时代，精准聚焦比信息量更重要。它**不关心**语气是否友好或事实是否正确，**只关心**“是否在回答这个问题”。


