[![zh-TW](https://img.shields.io/badge/lang-zh--TW-blue.svg)](./README.zh-TW.md)
# ComfyUI Text Processor

An advanced automation toolkit for ComfyUI, bridging the gap between raw data and generative AI. Features Batch Text Cleaning (for Img2Text), LLM Output Parsing, Dynamic Wildcards, and Logic Evaluation to streamline complex prompt engineering workflows.

![Workflow Demo](./examples/advanced_text_filter.png)

## 1. Advanced Text Filter Node (Core)

This is a powerful and flexible text processing node for ComfyUI, designed to automate and simplify your dynamic prompt workflows.

Whether you need to precisely extract sections from a large text block, batch replace keywords, or clean up messy text, this node provides robust support. Its **dual-output design** allows you to create complex **node chaining**, passing the remaining text from one node to the next for further processing.

### Core Features

* **Dual Outputs (Node Chaining)**: Provides `processed_text (Target)` and `remaining_text` outputs. You can chain the `remaining_text` to another `AdvancedTextFilter` node for multi-step text parsing.
* **17+ Operation Modes**:
    * Global Find/Replace/Extract
    * First-Match Split/Between
    * Format Cleanup
    * [New] LLM Output Parsing (JSON, Code blocks)
* Robust Error Handling (v1.1.5): The new `if_not_found` option allows you to choose the fallback behavior (return original, return empty, or trigger error) when a pattern isn't found, preventing batch workflow failures.
* **Powerful Regex Support**: A `use_regex` toggle switches all find and split operations to use Regular Expressions. **Now supports `DOTALL` mode** for multi-line matching.
* **Multi-Keyword Handling**: `Find/Replace` operations support multiple, comma-separated (`,`) targets in the `optional_text_input` field.
* **Input Flexibility**: An optional `external_text` input allows you to concatenate two text sources (like B-box data and a prompt) before processing.
* **Pre-processing**: Built-in `to UPPERCASE` / `to lowercase` functions to normalize case before any operation.

### Operation modes

The node's operations are split into three main categories:

#### A. Find / Replace / Extract (Global Operations)
This group finds and processes **all** matching instances. It uses the `optional_text_input` field as the target.
* **`find and remove`**: Removes all specified keywords.
* **`find and replace`**: Replaces all keywords with `replace_with_text`.
* **`find all (extract)`**: Extracts all matched keywords; returns original text with matches removed as "remaining".

#### B. Split & Between (First Match Only)
This group targets only the **first** matched instance. It uses the `start_text` and `end_text` fields.
* **`extract between`** / **`remove between`**
* **`extract before start text`** / **`remove after start text`**
* **`extract after start text`** / **`remove before start text`**

#### C. Text Cleanup
* `remove empty lines`, `remove newlines`, `strip lines (trim)`, `remove all whitespace`.

#### D. LLM Utilities (New in v1.1.5)
Specialized tools for processing raw outputs from Large Language Models (LLMs).
* **`LLM: extract code block (```)`**: Extracts code content strictly within triple backticks.
* **`LLM: extract JSON object ({...})`**: Locates and extracts the first valid JSON object structure, useful for chaining with JSON parsers.
* **`LLM: clean markdown formatting`**: Removes bold (`**`), italics (`*`), headers (`#`), and links to return clean, plain text.

#### E. Batch Operations (New in v1.2.0)
Designed for Img2Text workflows or bulk cleaning.
* **`batch replace (use replacement_rules)`**: Performs multiple find-and-replace operations in a single pass.
    * Uses the `replacement_rules` input box.
    * **Syntax:** `find_text -> replace_text` (one rule per line).
    * Example:
      ```text
      ugly -> beautiful
      bad hands -> detailed hands
      error_tag -> 
      ```
    * Supports Regex if `use_regex` is enabled.

---

## 2. Text Utilities

###  Text Input Node
A smart text combiner that merges up to 7 text sources into a single string.
* **Flexible Inputs:** Mix of 3 input slots (for chaining) and 4 text widgets (for manual input).
* **Auto-Cleaning:** Automatically filters out empty inputs to prevent double separators.
* **Fun Fallback:** If no input is provided, it returns a cute placeholder prompt.

###  Text Scraper Node
Fetches and formats headlines from any URL. Ideal for injecting real-time context into LLMs.
* **Simple Interface:** Just input a URL string.
* **Smart Parsing:** Uses heuristics to identify headlines (`h1`-`h4`, class names).
* **Safe:** Includes timeouts and error handling to prevent workflow freezing.

### Text Storage Nodes (Reader & Writer)
A persistent "clipboard" for ComfyUI. These nodes allow you to save and retrieve text data across different workflows or sessions. All data is securely stored in the `text_storage/` directory within the node folder.

#### **Text Storage (Writer)**
Saves text content to a file or internal database.
* **Inputs:**
    * `text_input`: The text content to save.
    * `filename_prefix`: Optional prefix for categorization (e.g., `ProjectA_`).
    * `save_name`: The main filename or key. Supports **Time Formatting** (e.g., `%Y-%m-%d`) and **Wildcards** (e.g., `***` for auto-incrementing 001, 002...).
    * `mode`:
        * **Add New (Auto Rename)**: Automatically avoids conflicts by renaming (e.g., `Log_2024-11-26_001.txt`).
        * **Overwrite Existing**: Replaces content if the name exists.
        * **Delete**: Removes the specified file/key.
    * **`storage_format` (New!)**:
        * `json`: Saves as a key inside the internal `text_storage.json` database.
        * `txt`: Saves as a standalone `.txt` file for easy external editing.

#### **Text Storage (Reader)**
Retrieves saved text content.
* **Unified List:** Automatically scans and lists both JSON keys and `.txt` files from the storage folder.
* **Passthrough:** Outputs the selected text content string.
* **> Important Note:** The dropdown list is generated when the node loads. If you have just saved a NEW file using the Writer node, you must **Refresh the ComfyUI Page (F5)** to see the new file appear in the Reader's list.

### Wildcards Processor (Dynamic Prompt Mixer)

Generate rich, dynamic prompts using wildcard syntax (e.g., `__style__`) and random choices (e.g., `{cat|dog}`). This node has been evolved into a powerful **7-slot mixer**.

* **Unified & Powerful (7-Slot Mixer)**:
    Replaces the previous Basic/Advanced split with a single, robust node. It features **7 input slots**, allowing you to combine manual text and wildcard files in complex layers.
* **Hybrid Inputs**:
    Each of the 7 slots offers both a **Text Box** (for manual prompt or `{choice}` syntax) and a **Dropdown Menu** (to select a wildcard file). They work together—you can use one, the other, or both simultaneously.
* **Smart "Random" Mode**:
    The dropdown menu includes a special **"Random"** option. When selected, it picks a random wildcard file from your collection for that specific slot, adding an extra layer of surprise.
* **Recursive Generation**:
    Fully supports nested wildcards (e.g., a wildcard file containing other `__wildcards__`).
* **Independent Seeds**:
    Each input slot uses a unique internal seed offset. This ensures that even if you use the same `{A|B}` syntax in multiple slots, they won't rigidly output the same result.
* **Cross-Platform**:
    Fully supports nested subdirectories and handles Windows/Linux/macOS file paths correctly.

---

## 3. Logic & Math Nodes (Simple Eval)

Safely evaluate Python expressions for dynamic calculations and logic flow. Powered by `simpleeval`.

###  Simple Eval (Integers / Floats / Strings)
Perform mathematical calculations or string manipulations without writing complex code.
* **3 Variants:** Dedicated nodes for `Integers`, `Floats`, and `Strings`.
* **Variables:** Supports inputs `a`, `b`, and `c`. You can use them in your expression (e.g., `(a + b) * 2` or `a + " " + b`).
* **Safe execution:** Restricted environment prevents unsafe code execution while allowing powerful logic.
* **Console Logging:** Optional toggle to print results to the console for debugging.

---

## 4. Image Utilities

###  Image Cropper
A handy utility to crop images directly within your workflow.
* **Targeted Cropping:** Easily remove unwanted borders or focus on specific subjects.
* **Batch Processing:** Supports cropping for image batches.

### Add Text to Image
Renders text onto images with advanced formatting options.
* **Auto-Scaling:** Text size automatically adjusts to fit the image width.
* **Background Box:** Supports semi-transparent background colors with padding.
* **Batch Support:** Can process image batches; text labels loop automatically if fewer than images.
* **Compatibility:** Outputs standard RGB images to ensure compatibility with Video/VAE nodes.

---

## Installation

### Method 1: Via ComfyUI Manager (Recommended)

This is the easiest way to install the node pack.

1.  Open **ComfyUI Manager** within your ComfyUI interface.
2.  Click on **"Custom Nodes Manager"**.
3.  Search for `ComfyUI Text Processor`.
4.  Click **Install** and wait for the process to complete.
5.  **Restart ComfyUI**.

### Method 2: Manual Installation

If you prefer terminal commands or don't use the Manager:

1.  Navigate to your custom nodes directory:
    ```bash
    cd ComfyUI/custom_nodes/
    ```
2.  Clone this repository:
    ```bash
    git clone https://github.com/rookiestar28/ComfyUI_Text_Processor.git
    ```
3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
4.  **Restart ComfyUI**.

---

###  Asset Setup (Optional)

* **Fonts:** Place your `.ttf` or `.otf` files in `ComfyUI/custom_nodes/ComfyUI_Text_Processor/fonts/` for the *Add Text to Image* node.
* **Wildcards:** Place your wildcard text files in `ComfyUI/wildcards/` or `ComfyUI/custom_nodes/ComfyUI_Text_Processor/wildcards/`.

<details>
<summary><strong>Click to see handy Regex Patterns (Cheat Sheet)</strong></summary>

### 🧹 Basic Cleaning

| Goal | Regex Pattern | Description |
| :--- | :--- | :--- |
| **Remove Extra Spaces** | `\s+` | Replaces multiple spaces with a single space. |
| **Remove Non-English** | `[^a-zA-Z0-9,\.\s]` | Removes everything except English letters, numbers, commas, and dots. |
| **Remove Digits/Numbers** | `\d+` | Removes all numbers (e.g., weights or unintended seeds). |
| **Clean Line Breaks** | `[\r\n]+` | Replaces new lines with commas (useful for flattening lists). |

### 🔍 Advanced Extraction & Filtering

| Goal | Regex Pattern | Description |
| :--- | :--- | :--- |
| **Remove HTML Tags** | `<[^>]*>` | Cleans up text scraped from websites (removes div, br tags, etc.). |
| **Remove Weight Brackets** | `\(([^)]*:\d+(?:\.\d+)?)\)` | Removes standard prompt weights like `(word:1.2)`. |
| **Extract Email** | `[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}` | Extracts email addresses from mixed text. |
| **Match Wildcards** | `__\w+__` | Matches typical wildcard syntax like `__character__`. |

</details>

---

<div align="center">
Made with ❤️ for the ComfyUI Community
</div>