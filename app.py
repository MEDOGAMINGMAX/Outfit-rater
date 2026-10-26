import os, json, uuid
from flask import Flask, request, jsonify, send_from_directory
from PIL import Image
from dotenv import load_dotenv
from google import genai

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
MODEL = "gemini-3.5-flash-lite"

app = Flask(__name__)
app.json.ensure_ascii = False

DIR = os.path.expanduser("~/wardrobe")
DB = os.path.join(DIR, "wardrobe.json")
os.makedirs(DIR, exist_ok=True)

RATE = """قيّم الإطلالة في الصورة من 10.
ارجع JSON فقط بالشكل ده:
{"score": رقم, "comment": "تعليق قصير بالمصري", "suggestion": "لو التقييم أقل من 7 اقترح تبديل قطعة محددة، وإلا اتركها فاضية"}"""

ITEM = """حلل قطعة الملابس في الصورة. ارجع JSON فقط بالشكل ده:
{"type": "نوع القطعة مثل قميص أو بنطلون أو جاكيت أو جزمة", "color": "اللون", "style": "رسمي أو كاجوال أو رياضي", "desc": "وصف قصير جدا"}"""

def readDb():
    if os.path.exists(DB):
        with open(DB, encoding="utf-8") as f:
            return json.load(f)
    return []

def writeDb(items):
    with open(DB, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False)

def ask(contents):
    r = client.models.generate_content(
        model=MODEL,
        contents=contents,
        config={"response_mime_type": "application/json"},
    )
    data = json.loads(r.text)
    return data[0] if isinstance(data, list) and data else data

def openImage(file):
    img = Image.open(file)
    img.load()
    img = img.convert("RGB")
    img.thumbnail((1024, 1024))
    return img

@app.route("/")
def home():
    return "Outfit Rater is running"

@app.route("/rate", methods=["POST"])
def rate():
    file = request.files.get("image")
    if not file:
        return jsonify({"error": "no image"}), 400
    try:
        img = openImage(file)
    except Exception:
        return jsonify({"error": "invalid image"}), 400
    try:
        return jsonify(ask([img, RATE]))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/add-item", methods=["POST"])
def addItem():
    file = request.files.get("image")
    if not file:
        return jsonify({"error": "no image"}), 400
    try:
        img = openImage(file)
    except Exception:
        return jsonify({"error": "invalid image"}), 400
    try:
        info = ask([img, ITEM])
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    iid = uuid.uuid4().hex[:8]
    img.save(os.path.join(DIR, iid + ".jpg"), quality=85)
    info["id"] = iid
    items = readDb()
    items.append(info)
    writeDb(items)
    return jsonify(info)

@app.route("/wardrobe")
def wardrobe():
    return jsonify(readDb())

@app.route("/img/<iid>")
def serveImg(iid):
    return send_from_directory(DIR, iid + ".jpg")

@app.route("/outfit", methods=["POST"])
def outfit():
    occasion = request.form.get("occasion", "")
    items = readDb()
    if len(items) < 2:
        return jsonify({"error": "add more items first"}), 400
    lines = "\n".join(i["id"] + ": " + i["type"] + " " + i["color"] + " " + i["style"] for i in items)
    prompt = ("المناسبة: " + occasion + "\nدي قطع الدولاب:\n" + lines +
              "\nاختار طقم كامل مناسب من القطع دي بس. ارجع JSON فقط بالشكل ده: "
              '{"ids": ["id1", "id2"], "comment": "ليه الطقم مناسب بالمصري"}')
    try:
        return jsonify(ask([prompt]))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
