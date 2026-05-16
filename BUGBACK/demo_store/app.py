from flask import Flask, request, redirect, url_for, render_template_string, session, jsonify

app = Flask(__name__)
app.secret_key = "bugback-demo-secret"

BASE_CSS = """
<style>
body { font-family: Inter, Arial, sans-serif; margin: 0; background: #f6f7fb; color: #1f2937; }
.nav { background:#111827; color:white; padding:16px 28px; display:flex; justify-content:space-between; align-items:center; }
.container { max-width: 920px; margin: 36px auto; padding: 0 20px; }
.card { background:white; border-radius:18px; padding:24px; box-shadow:0 12px 30px rgba(0,0,0,.08); margin-bottom:20px; }
button, .btn { border:0; padding:12px 16px; border-radius:12px; background:#2563eb; color:white; font-weight:700; cursor:pointer; text-decoration:none; display:inline-block; }
button.secondary { background:#111827; }
input { padding:12px 14px; border:1px solid #d1d5db; border-radius:12px; width:230px; }
.price { font-size: 30px; font-weight: 800; }
.good { color:#047857; font-weight:700; }
.bad { color:#dc2626; font-weight:700; }
.grid { display:grid; grid-template-columns:1fr 1fr; gap:20px; }
.small { color:#6b7280; font-size:14px; }
.freeze-overlay { display:none; position:fixed; inset:0; background:rgba(17,24,39,.88); color:white; align-items:center; justify-content:center; flex-direction:column; z-index:20; }
.spinner { width:54px; height:54px; border:6px solid #9ca3af; border-top-color:white; border-radius:50%; animation: spin 1s linear infinite; margin-bottom:16px; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
"""

def cart_state():
    return {
        "item": session.get("item", False),
        "discount": session.get("discount", False),
        "charged": session.get("charged", 0),
    }

@app.route("/")
def home():
    session.setdefault("item", False)
    session.setdefault("discount", False)
    session.setdefault("charged", 0)
    return render_template_string(BASE_CSS + """
    <div class="nav"><b>BugBack Demo Store</b><span class="small">Intentionally broken test site</span></div>
    <div class="container">
      <div class="card">
        <h1>NVIDIA GPU</h1>
        <p class="small">Demo product used for autonomous browser reproduction.</p>
        <p class="price">$3000.00</p>
        <form action="/add_to_cart" method="post">
          <button id="add-to-cart" type="submit">Add to cart</button>
          <button id="open-cart" class="secondary" type="button" onclick="freezeCart()">Open cart drawer</button>
        </form>
      </div>
      <div class="grid">
        <div class="card"><h3>Bug 1</h3><p>Discount code <b>SAVE20</b> appears in cart but disappears at checkout.</p></div>
        <div class="card"><h3>Bug 2</h3><p>Payment retry accidentally double-charges the customer.</p></div>
        <div class="card"><h3>Bug 3</h3><p>Opening the cart drawer freezes the page.</p></div>
      </div>
    </div>
    <div id="freeze" class="freeze-overlay"><div class="spinner"></div><h2>Cart drawer stuck loading...</h2><p>This simulates a frontend freeze.</p></div>
    <script>
      function freezeCart(){
        document.getElementById('freeze').style.display = 'flex';
        window.__BUGBACK_FRONTEND_FREEZE__ = true;
      }
    </script>
    """)

@app.route("/add_to_cart", methods=["POST"])
def add_to_cart():
    session["item"] = True
    return redirect(url_for("cart"))

@app.route("/cart", methods=["GET", "POST"])
def cart():
    if request.method == "POST":
        code = request.form.get("discount_code", "").strip().upper()
        if code == "SAVE20":
            session["discount"] = True
        return redirect(url_for("cart"))

    discount = session.get("discount", False)
    total = 80 if discount else 100
    return render_template_string(BASE_CSS + """
    <div class="nav"><b>BugBack Demo Store</b><a class="btn" href="/">Home</a></div>
    <div class="container">
      <div class="card">
        <h1>Your Cart</h1>
        <p>Wireless Headphones: $100.00</p>
        {% if discount %}<p id="discount-line" class="good">SAVE20 applied: -$20.00</p>{% else %}<p id="discount-line" class="bad">No discount applied</p>{% endif %}
        <p id="cart-total" class="price">Total: ${{ total }}.00</p>
        <form method="post">
          <input id="discount-code" name="discount_code" placeholder="Enter SAVE20" />
          <button id="apply-discount" type="submit">Apply discount</button>
        </form>
        <br/>
        <a id="checkout-link" class="btn" href="/checkout">Proceed to checkout</a>
      </div>
    </div>
    """, discount=discount, total=total)

@app.route("/checkout")
def checkout():
    # INTENTIONAL BUG: promo-engine-v2 drops the discount during checkout refresh.
    session["discount"] = False
    return render_template_string(BASE_CSS + """
    <div class="nav"><b>BugBack Demo Store</b><a class="btn" href="/cart">Cart</a></div>
    <div class="container">
      <div class="card">
        <h1>Checkout</h1>
        <p id="checkout-discount" class="bad">Discount missing at checkout</p>
        <p id="checkout-total" class="price">Total: $100.00</p>
        <form action="/pay" method="post">
          <button id="pay-button" type="submit">Pay now</button>
        </form>
      </div>
    </div>
    """)

@app.route("/pay", methods=["POST"])
def pay():
    # INTENTIONAL BUG: payment-retry-handler creates two authorizations.
    session["charged"] = 2
    return redirect(url_for("confirmation"))

@app.route("/confirmation")
def confirmation():
    charged = session.get("charged", 0)
    return render_template_string(BASE_CSS + """
    <div class="nav"><b>BugBack Demo Store</b><a class="btn" href="/">Home</a></div>
    <div class="container">
      <div class="card">
        <h1>Order confirmation</h1>
        <p id="charge-count" class="{{ 'bad' if charged > 1 else 'good' }}">Payment authorizations: {{ charged }}</p>
        <p id="payment-message">{{ 'Customer was charged twice.' if charged > 1 else 'Customer was charged once.' }}</p>
      </div>
    </div>
    """, charged=charged)

@app.route("/reset", methods=["POST", "GET"])
def reset():
    session.clear()
    return redirect(url_for("home"))

@app.route("/api/state")
def api_state():
    return jsonify(cart_state())

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=True)
