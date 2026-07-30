PROTOTYPE_API_BINDING = "comfy_api.v0_0_2"
PRODUCTION_ENABLED = False
SELECTED_NODE_ID = "TextInput"


def build_text_input_v3_prototype(io):
    class TextInputV3Prototype(io.ComfyNode):
        @classmethod
        def define_schema(cls):
            return io.Schema(
                node_id=SELECTED_NODE_ID,
                display_name="Text Input",
                category="ComfyUI Text Processor",
                description=(
                    "Joins up to seven text inputs into one string with a "
                    "configurable separator."
                ),
                search_aliases=[
                    "text input",
                    "join text",
                    "merge text",
                    "combine strings",
                    "prompt join",
                ],
                inputs=[
                    io.String.Input("separator", default=" "),
                    io.String.Input("text1", optional=True),
                    io.String.Input("text2", optional=True),
                    io.String.Input("text3", optional=True),
                    io.String.Input("text4", optional=True, default=""),
                    io.String.Input("text5", optional=True, default=""),
                    io.String.Input("text6", optional=True, default=""),
                    io.String.Input("text7", optional=True, default=""),
                ],
                outputs=[
                    io.String.Output(display_name="STRING"),
                ],
            )

        @classmethod
        def execute(
            cls,
            separator,
            text1="",
            text2="",
            text3="",
            text4="",
            text5="",
            text6="",
            text7="",
        ):
            texts = [
                text
                for text in (text1, text2, text3, text4, text5, text6, text7)
                if text
            ]
            if not texts:
                return io.NodeOutput(
                    "A cute little monster holding a sign with big text: "
                    "GIVE ME INPUT!"
                )
            return io.NodeOutput(separator.join(texts))

    return TextInputV3Prototype
