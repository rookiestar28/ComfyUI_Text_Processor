# Advanced Text Filter Node for ComfyUI

This is a powerful and flexible text processing node for ComfyUI, designed to automate and simplify your dynamic prompt workflows.

Whether you need to precisely extract sections from a large text block, batch replace keywords, or clean up messy text, this node provides robust support. Its **dual-output design** allows you to create complex **node chaining**, passing the remaining text from one node to the next for further processing.

## Core Features

* **Dual Outputs (Node Chaining)**: Provides `processed_text (Target)` and `remaining_text` outputs. You can chain the `remaining_text` to another `AdvancedTextFilter` node for multi-step text parsing.
* **13+ Operation Modes**:
    * Global Find/Replace/Extract
    * First-Match Split/Between
    * Format Cleanup
* **Powerful Regex Support**: A `use_regex` toggle switches all find and split operations to use Regular Expressions for complex pattern matching.
* **Multi-Keyword Handling**: `Find/Replace` operations support multiple, comma-separated (`,`) targets in the `optional_text_input` field.
* **Input Flexibility**: An optional `external_text` input allows you to concatenate two text sources (like B-box data and a prompt) before processing.
* **Pre-processing**: Built-in `to UPPERCASE` / `to lowercase` functions to normalize case before any operation.


## Operation modes

The node's operations are split into three main categories:

### 1. Find / Replace / Extract (Global Operations)

This group finds and processes **all** matching instances. It uses the `optional_text_input` field as the target.

* **`find and remove (use optional_text)`**
    * Removes all keywords specified in `optional_text_input`.
* **`find and replace (use optional_text, replace_with_text)`**
    * Replaces all keywords from `optional_text_input` with the content of `replace_with_text`.
* **`find all (extract) (use optional_text)`**
    * **Processed:** Extracts all matched keywords (separated by newlines).
    * **Remaining:** The original text with all matches removed.

### 2. Split & Between (First Match Only)

This group targets only the **first** matched instance. It uses the `start_text` and `end_text` fields.

* **`extract between`** / **`remove between`**
    * Extracts or removes the content found between `start_text` and `end_text`.
* **`extract before start text`** / **`remove after start text`**
    * Extracts everything *before* the `start_text` (and removes everything after).
* **`extract after start text`** / **`remove before start text`**
    * Extracts everything *after* the `start_text` (and removes everything before).

### 3. Text Cleanup

These are simple formatting tools. The `remaining_text` output is typically empty.

* `remove empty lines`: Removes all blank lines or lines containing only whitespace.
* `remove newlines`: Flattens all text into a single line.
* `strip lines (trim)`: Removes leading and trailing whitespace from every line.
* `remove all whitespace (keep newlines)`: Removes all spaces and tabs, but preserves the line structure.
---

## Installation

1.  `cd` into your `ComfyUI/custom_nodes/` directory.
2.  Clone this repository:
    ```bash
    git clone [https://github.com/rookiestar28/ComfyUI_Text_Processor.git](https://github.com/rookiestar28/ComfyUI_Text_Processor.git)
    ```
3.  Restart ComfyUI.
---

# Advanced Text Filter Node for ComfyUI

這是一個功能強大且高度靈活的文字處理節點，專為 ComfyUI 設計，旨在自動化和簡化您的動態提示詞（Dynamic Prompts）工作流。

無論您是需要從一大段文本中精確提取特定部分、批量替換關鍵字，還是清理雜亂的文字，這個節點都能提供強大的支援。其**雙重輸出設計**允許您建立複雜的**節點串聯（Chaining）**，將一個節點的剩餘文本傳遞給下一個節點進行進一步處理。

## 核心特色

* **雙重輸出（節點串聯）**：提供 `processed_text (Target)` 和 `remaining_text` 兩個輸出。您可以將 `remaining_text` 連接到另一個 `AdvancedTextFilter` 節點，實現多步驟的文本解析。
* **13+ 種操作模式**：
    * 全局查找/替換 (`Find/Replace/Extract`)
    * 首次匹配分割 (`Split/Between`)
    * 格式清理 (`Cleanup`)
* **強大的 Regex 支援**：`use_regex` 開關可將所有查找和分割操作切換為使用正規表示式，實現複雜的模式匹配。
* **多關鍵字處理**：`Find/Replace` 操作支援在 `optional_text_input` 欄位中使用逗號 (`,`) 分隔多個查找目標。
* **輸入靈活性**：可選的 `external_text` 輸入，允許您在處理前將兩段文本（如 B-box 數據和提示詞）進行合併。
* **預處理**：內建 `to UPPERCASE` / `to lowercase` 功能，在執行任何操作前統一大小寫。
---

## 操作模式

### 1. Find / Replace / Extract (全局操作)

這組操作會查找並處理**所有**匹配的實例。它們使用 `optional_text_input` 作為查找目標。

* **`find and remove (use optional_text)`**
    * 移除所有在 `optional_text_input` 中指定的關鍵字。
* **`find and replace (use optional_text, replace_with_text)`**
    * 將所有 `optional_text_input` 中的關鍵字替換為 `replace_with_text` 的內容。
* **`find all (extract) (use optional_text)`**
    * **Processed:** 提取所有匹配的關鍵字（用換行符分隔）。
    * **Remaining:** 原始文本中移除了所有匹配項的內容。

### 2. Split & Between (首次匹配)

這組操作只會針對**第一個**匹配的實例進行操作。它們使用 `start_text` 和 `end_text`。

* **`extract between`** / **`remove between`**
    * 提取或移除 `start_text` 和 `end_text` 之間的內容。
* **`extract before start text`** / **`remove after start text`**
    * 提取 `start_text` 之前的所有內容（並移除之後的）。
* **`extract after start text`** / **`remove before start text`**
    * 提取 `start_text` 之後的所有內容（並移除之前的）。

### 3. Text Cleanup (文本清理)

這些是簡單的格式化工具，`remaining_text` 輸出通常為空。

* `remove empty lines`: 移除所有空行或只包含空白的行。
* `remove newlines`: 將所有文本合併為單一行。
* `strip lines (trim)`: 移除每一行開頭和結尾的空白。
* `remove all whitespace (keep newlines)`: 移除所有空格和 Tab，但保留換行結構。
---
## 安裝

1.  `cd` 進入您的 `ComfyUI/custom_nodes/` 資料夾。
2.  克隆本倉庫：
    ```bash
    git clone [https://github.com/rookiestar28/ComfyUI_Text_Processor.git](https://github.com/rookiestar28/ComfyUI_Text_Processor.git)
    ```
3.  重新啟動 ComfyUI。