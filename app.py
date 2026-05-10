from flask import Flask, render_template, redirect, url_for, request, jsonify, session
from google import genai
from google.genai import types
import sqlite3
import json

app = Flask(__name__)
app.secret_key = "laptopshop_secret_key"
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

# Khởi tạo database
def get_db():
    db = sqlite3.connect('orders.db')
    db.row_factory = sqlite3.Row
    return db

def init_db():
    db = get_db()
    db.execute('''CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        items TEXT NOT NULL,
        total REAL NOT NULL,
        status TEXT DEFAULT 'Chờ xác nhận',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    db.commit()

init_db()

# Khởi tạo Gemini Client
GEMINI_API_KEY = "AIzaSyB2XvyXEeInfK4o3CLhlpcoPRs4CqcJlZE"
client = genai.Client(api_key=GEMINI_API_KEY)

SYSTEM_PROMPT = """Bạn là nhân viên tư vấn laptop chuyên nghiệp của LaptopShop. 
Nhiệm vụ: Chỉ tư vấn về các mẫu laptop có sẵn trong cửa hàng. Không trả lời các chủ đề ngoài lề.
Danh sách sản phẩm và giá:
- ASUS VivoBook 15: 12,990,000đ
- Dell Inspiron 15: 15,490,000đ
- HP Pavilion 14: 13,990,000đ
- Lenovo IdeaPad 3: 11,990,000đ
- MacBook Air M2: 28,990,000đ
- Acer Aspire 5: 10,990,000đ
Phong cách: Thân thiện, ngắn gọn, hỗ trợ nhiệt tình bằng tiếng Việt."""

products = [
    {"id": 1,  "name": "MacBook Air M2 16GB",          "price": 28990000, "brand": "apple",  "image": "https://cdn2.fptshop.com.vn/unsafe/750x0/filters:format(webp):quality(75)/macbook_air_13_m2_starlight_1_24bf8f9188.png"},
    {"id": 2,  "name": "ASUS ZenBook S14",              "price": 32990000, "brand": "asus",   "image": "https://cdn2.fptshop.com.vn/unsafe/750x0/filters:format(webp):quality(75)/asus_zenbook_s14_ux5406aa_trang_01_e95a112e80.png"},
    {"id": 3,  "name": "Lenovo ThinkBook 16 Gen 7",     "price": 18990000, "brand": "lenovo", "image": "https://cdn2.fptshop.com.vn/unsafe/750x0/filters:format(webp):quality(75)/lenovo_loq_15arp9_1_d659ef3c4b.png"},
    {"id": 4,  "name": "Lenovo ThinkPad E16 Gen 3",     "price": 22990000, "brand": "lenovo", "image": "https://cdn2.fptshop.com.vn/unsafe/750x0/filters:format(webp):quality(75)/lenovo_gaming_loq_15irx9_1_afcaf5d0a0.png"},
    {"id": 5,  "name": "Dell Latitude 5450",            "price": 24990000, "brand": "dell",   "image": "https://cdn2.fptshop.com.vn/unsafe/750x0/filters:format(webp):quality(75)/dell_latitude_15_3540_9950b79986.png"},
    {"id": 6,  "name": "HP 240 G10 i7",                "price": 15490000, "brand": "hp",     "image": "https://cdn2.fptshop.com.vn/unsafe/750x0/filters:format(webp):quality(75)/hp_probook_440_g10_66e5fca614.png"},
    {"id": 7,  "name": "Dell XPS 13 OLED",             "price": 38990000, "brand": "dell",   "image": "https://cdn2.fptshop.com.vn/unsafe/750x0/filters:format(webp):quality(75)/dell_xps_13_9350_graphite_1_49d3d81742.png"},
    {"id": 8,  "name": "Microsoft Surface Laptop 7",   "price": 34990000, "brand": "other",  "image": "https://cdn2.fptshop.com.vn/unsafe/750x0/filters:format(webp):quality(75)/2021_1_12_637460438030330849_microsoft-surface-pro-7-i5-1035g4-bac-2.png"},
    {"id": 9,  "name": "LG Gram 14",                   "price": 29990000, "brand": "other",  "image": "https://cdn2.fptshop.com.vn/unsafe/1920x0/filters:format(webp):quality(75)/2023_6_9_638219256198001537_lg-gram-style-14z90rs-gah54a5-i5-1340p-trang-3.jpg"},
    {"id": 10, "name": "ASUS TUF Gaming F16",          "price": 23990000, "brand": "asus",   "image": "https://cdn2.fptshop.com.vn/unsafe/750x0/filters:format(webp):quality(75)/asus_tuf_gaming_f16_fx608jmi_gray_01_36b6d23e99.png"},
    {"id": 11, "name": "MSI Katana 15 RTX 4060",       "price": 27990000, "brand": "other",  "image": "https://cdn2.fptshop.com.vn/unsafe/750x0/filters:format(webp):quality(75)/2023_3_9_638139851534926926_msi-gaming-katana-15-b13v-den-1.jpg"},
    {"id": 12, "name": "HP OMEN 16 RTX 4070",          "price": 39990000, "brand": "hp",     "image": "https://cdn2.fptshop.com.vn/unsafe/750x0/filters:format(webp):quality(75)/hp_gaming_omen_16_den_01_e60b948004.png"},
]

cart = []

PRICE_RANGES = {
    "under12":  (0,          12000000),
    "12to15":   (12000000,   15000000),
    "15to20":   (15000000,   20000000),
    "over20":   (20000000,   999999999),
}

@app.route("/")
def index():
    query       = request.args.get("q", "").strip().lower()
    brand       = request.args.get("brand", "").strip().lower()
    price_range = request.args.get("price", "").strip().lower()
    filtered = products
    if query:
        filtered = [p for p in filtered if query in p["name"].lower()]
    if brand and brand != "all":
        filtered = [p for p in filtered if p["brand"] == brand]
    if price_range and price_range in PRICE_RANGES:
        lo, hi = PRICE_RANGES[price_range]
        filtered = [p for p in filtered if lo <= p["price"] <= hi]
    return render_template("index.html", products=filtered, cart=cart, query=query, brand=brand, price_range=price_range)

@app.route("/add/<int:product_id>")
def add_to_cart(product_id):
    product = next((p for p in products if p["id"] == product_id), None)
    if product:
        item = product.copy()
        item["cart_id"] = len(cart) + 1
        cart.append(item)
    return redirect(url_for("index"))

@app.route("/remove/<int:cart_id>")
def remove_from_cart(cart_id):
    global cart
    cart = [item for item in cart if item["cart_id"] != cart_id]
    return redirect(url_for("cart_page"))

@app.route("/clear")
def clear_cart():
    global cart
    cart = []
    return redirect(url_for("index"))

@app.route("/cart")
def cart_page():
    total = sum(item["price"] for item in cart)
    return render_template("cart.html", cart=cart, total=total)

@app.route('/order', methods=['POST'])
def place_order():
    total = sum(item['price'] for item in cart)
    if not cart:
        return redirect('/cart')
    items_json = json.dumps(cart, ensure_ascii=False)
    db = get_db()
    db.execute('INSERT INTO orders (items, total) VALUES (?, ?)', (items_json, total))
    db.commit()
    return redirect('/order-success')

@app.route('/order-success')
def order_success():
    return render_template('order_success.html')

@app.route('/orders')
def orders():
    db = get_db()
    all_orders = db.execute('SELECT * FROM orders ORDER BY created_at DESC').fetchall()
    return render_template('orders.html', orders=all_orders)

@app.route('/orders/delete/<int:order_id>')
def delete_order(order_id):
    db = get_db()
    db.execute('DELETE FROM orders WHERE id = ?', (order_id,))
    db.commit()
    return redirect('/orders')

@app.route('/orders/update/<int:order_id>', methods=['POST'])
def update_order(order_id):
    status = request.form.get('status')
    db = get_db()
    db.execute('UPDATE orders SET status = ? WHERE id = ?', (status, order_id))
    db.commit()
    return redirect('/orders')

@app.route("/chat", methods=["POST"])
def chat():
    try:
        user_msg = request.json.get("message", "")
        if not user_msg:
            return jsonify({"reply": "Chào bạn! Mình có thể giúp gì cho bạn không?"})
        response = client.models.generate_content(
            model="gemini-2.0-flash-lite",
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.7,
                max_output_tokens=200,
            ),
            contents=[user_msg]
        )
        return jsonify({"reply": response.text})
    except Exception as e:
        print(f"--- LỖI GEMINI: {e} ---")
        return jsonify({"reply": "Rất tiếc, mình đang gặp sự cố kết nối. Bạn thử lại sau nhé!"})

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)