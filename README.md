[![zh-TW](https://img.shields.io/badge/lang-zh--TW-blue.svg)](./README.zh-TW.md)
# ComfyUI Text Processor

A comprehensive suite of text processing nodes for ComfyUI, designed to enhance prompt engineering, text manipulation, and automated workflows.

## 1. Advanced Text Filter Node (Core)

This is a powerful and flexible text processing node for ComfyUI, designed to automate and simplify your dynamic prompt workflows.

Whether you need to precisely extract sections from a large text block, batch replace keywords, or clean up messy text, this node provides robust support. Its **dual-output design** allows you to create complex **node chaining**, passing the remaining text from one node to the next for further processing.

### Core Features

* **Dual Outputs (Node Chaining)**: Provides `processed_text (Target)` and `remaining_text` outputs. You can chain the `remaining_text` to another `AdvancedTextFilter` node for multi-step text parsing.
* **13+ Operation Modes**:
    * Global Find/Replace/Extract
    * First-Match Split/Between
    * Format Cleanup
* **Powerful Regex Support**: A `use_regex` toggle switches all find and split operations to use Regular Expressions for complex pattern matching.
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

---

## 2. Additional Tools

### 📝 Text Input Node
A smart text combiner that merges up to 7 text sources into a single string.
* **Flexible Inputs:** Mix of 3 input slots (for chaining) and 4 text widgets (for manual input).
* **Auto-Cleaning:** Automatically filters out empty inputs to prevent double separators.
* **Fun Fallback:** If no input is provided, it returns a cute placeholder prompt.

### 📰 Text Scraper Node
Fetches and formats headlines from any URL. Ideal for injecting real-time context into LLMs.
* **Simple Interface:** Just input a URL string.
* **Smart Parsing:** Uses heuristics to identify headlines (`h1`-`h4`, class names).
* **Safe:** Includes timeouts and error handling to prevent workflow freezing.

### 💾 Text Storage Node
A persistent "clipboard" for ComfyUI. Save, load, and manage text snippets directly within the interface.
* **Modes:** `Save`, `Load`, `Remove`, `Replace`.
* **Local Storage:** Saves data to `text_storage.json` inside the node folder (easy backup).
* **Auto-Refresh:** Automatically updates the dropdown list when new text is saved.

### 🃏 Wildcards Node (Basic & Advanced)
Generate dynamic prompts using wildcard syntax (e.g., `__style__`) and random choices (e.g., `{cat|dog}`).
* **Two Versions:**
    * **Basic:** Simple text box interface, compact.
    * **Advanced:** Adds dropdown menus to select wildcard files directly from your `wildcards` folder.
* **Cross-Platform:** Fully supports Windows and Linux/macOS paths.
* **Independent Seeds:** Each input field uses a unique random seed offset to ensure variety.

### 🖼️ Add Text to Image
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
    git clone [https://github.com/rookiestar28/ComfyUI_Text_Processor.git](https://github.com/rookiestar28/ComfyUI_Text_Processor.git)
    ```
3.  **Restart ComfyUI**.

---

### 📂 Asset Setup (Optional)

* **Fonts:** Place your `.ttf` or `.otf` files in `ComfyUI/custom_nodes/ComfyUI_Text_Processor/fonts/` for the *Add Text to Image* node.
* **Wildcards:** Place your wildcard text files in `ComfyUI/wildcards/` or `ComfyUI/custom_nodes/ComfyUI_Text_Processor/wildcards/`.