# Instruction for Test Case Generation

## Workflow overview

Use available tool to create a TODO list below, and finish it step by step.

```
- [] step0: Input Conformation: Display input you acquired from context to user
  - Finish the step and display result to user.

- [] step1: Generation Style: 固定为 Follow the input，直接进入 step2

- [] step2: Context Gathering: Search the workspace and gather business knowledge and customized skills based on `Business Identifier`

- [] step3: Test Case Generation: Follow the input style, convert test_analysis.md to case.md
  - Framework generation
  - Display the framework to user by displaying path of the html file
  - Detailed case generation
  - Display the framework to user by displaying path of the html file
```

## step0. Input Confirmation

Go through the working dir, check whether the documents/sources below are available:

[ ] Input document (Required)
[ ] Business Identifier (Required)
[ ] Other input(Optional): PRD, Tech design, spec.md, Codebase, Figma

Show the check result to the user, and ask the user to provide additional information if the required input is missing.

## step1. Generation Style（固定）

Web e2e 场景下 `Generation Style` 固定为 `Follow the input`，直接进入 step2。

## step2. Context Gathering

**Context Space**

- Search the workspace, especially the Knowledge Base dir to find reference about:
  - Business Knowledge
  - Test case writing rules
  - Regression test cases
- Search strategy
  - For Knowledge Base search, search `business_knowledge/${Business Identifier}` dir
  - For business customized skills, search `skills/custom/${Business Identifier}` dir

**Context Priority**

- Information from business customized knowledge/skill has a higher priority than the general information.
- If customized information contradicts with general information, follow the customized information and tell the user your choice. 

**How to use context**

- Write a plan about how to update input_document based on the context
- Ask the user's confirmation and then execute the plan to update the `input_document.md`

## step3. Test Case Generation (Follow the input)

#### General process

- [**FORCE**] Read `references/test_case_grammar.md`, understand the grammar of test cases. 
- [**FORCE**] Read `references/ab_setting_rule.md` to understand how to organize case structure based on A/B experiment setting.
- Convert the input document into `case.md`, be loyal to the original input document.
- Use `scripts/case_grammar_check.py` to check generated test case.
- Read `references/test_case_grammar.md` **again** to check whether current case is consistent with test case grammar.

#### Special Post process

- `case_mode` == `Web`
  - Rule about how to start the case: Require `访问 $URL` in `前置条件` node, and the `操作步骤` node should start with the assumption that the page has been browsed.
    - Add URL to `前置条件`: Add `访问: $URL \n` at the beginning of each `前置条件` node.
    - The `$URL` should come from `input_document` or from context. If there is no specific URL information, ask the user to supply.
    - If there are existing content like `打开浏览器` and `访问 $URL` in `操作步骤` after the `前置条件` node, remove them and only keep actions after the browsing step.
  - Add `e2e` tag to `前置条件`, append it to the end of `前置条件` content with a new line.

#### Generation Instructions

**Separated Assertions**  
Each assertion should be an independent `预期结果` node, DO NOT aggregate them unless you feel necessary.

**Handle Aggregated steps and their assertions**  
For input with aggregated steps and assertions while then NEED to be split:

| 操作步骤                                     | 预期结果                                        |
| -------------------------------------------- | ----------------------------------------------- |
| 1. step1<br>2. step2<br>3. step3<br>4. step4 | 1. assertion1<br>2. assertion2<br>3. assertion3 |

> For instance, if the real logical sequence of test execution of the table above is: 
> step1 -> step2 -> assertion1 -> step3 -> step4 -> assertion2 -> assertion3

Then the generated case should be like:

```text
## **操作步骤** 1. step1
2. step2
### **预期结果** assertion1
### **操作步骤** 1. step3
2. step4
#### **预期结果** assertion1
#### **预期结果** assertion1
```