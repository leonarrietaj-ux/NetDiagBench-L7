import urllib.request
import json

def check_models():
    url = "http://127.0.0.1:11434/api/tags"
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models = data.get("models", [])
            print(f"Total models in Ollama: {len(models)}")
            for m in models:
                name = m.get("name")
                digest = m.get("digest")
                size = m.get("size")
                details = m.get("details", {})
                family = details.get("family")
                param_size = details.get("parameter_size")
                quant = details.get("quantization_level")
                print(f"Name: {name}")
                print(f"  Digest: {digest}")
                print(f"  Size: {size} bytes ({round(size / (1024**3), 2)} GB)")
                print(f"  Family: {family}")
                print(f"  Parameter Size: {param_size}")
                print(f"  Quantization: {quant}")
                print("-" * 50)
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    check_models()
