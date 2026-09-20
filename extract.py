import os
import inspect

try:
    from strands.models.openai import OpenAIModel
    with open("scratch/openai_model_source.txt", "w") as f:
        f.write(inspect.getsource(OpenAIModel))
        
    import strands.middlewares
    with open("scratch/middlewares_dir.txt", "w") as f:
        f.write(str(dir(strands.middlewares)))
except Exception as e:
    with open("scratch/error.txt", "w") as f:
        f.write(str(e))
