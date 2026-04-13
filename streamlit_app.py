import streamlit as st
import json
import os
import io
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics.widgets.markers import makeMarker

# --- Configuration & Styling ---
st.set_page_config(page_title="KE Billing Pro - Web", page_icon="⚡", layout="wide")

# Custom CSS for Premium Look
st.markdown("""
    <style>
    .main { background-color: #050505; color: #ffffff; }
    .stButton>button { width: 100%; border-radius: 12px; height: 3em; font-weight: bold; }
    .stMetric { background-color: #111111; padding: 15px; border-radius: 15px; border: 1px solid #333333; }
    div[data-testid="stSidebar"] { background-color: #0c0c0c; }
    </style>
""", unsafe_allow_html=True)

DEFAULT_SETS = {
    "ke_slabs": [[100, 16.48], [300, 22.14], [700, 29.33], [999999, 32.71]],
    "fixed_charge": 600.0,
    "sales_tax": 350.0,
    "company_name": "KE Billing Pro"
}

# --- Shared Logic ---
def calculate_bill(units, settings):
    slabs = settings.get('ke_slabs', DEFAULT_SETS['ke_slabs'])
    cost = 0
    prev_limit = 0
    breakdown = []
    
    remaining = units
    curr_prev = 0
    for limit, rate in slabs:
        if remaining > 0:
            u_in_slab = min(remaining, limit - curr_prev)
            cost += u_in_slab * rate
            breakdown.append({'slab': limit, 'units': u_in_slab, 'rate': rate, 'subtotal': u_in_slab * rate})
            remaining -= u_in_slab
            curr_prev = limit
            
    total = cost + float(settings.get('fixed_charge', 600)) + float(settings.get('sales_tax', 350))
    return total, cost, breakdown

def generate_pdf(data):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    
    # Logic extracted from main.py
    p = data['profile']
    s = data['settings']
    res_total = data['total']
    units = data['units']
    c_prev = data['prev_reading']
    cur_reading = data['curr_reading']
    b_month = data['month']
    curr_date = datetime.now().strftime('%d %b %Y')

    # Header
    if os.path.exists('owais_logo.png'):
        c.drawImage('owais_logo.png', 40, height - 70, width=70, height=40, preserveAspectRatio=True, mask='auto')
    
    c.setFont("Helvetica-Bold", 14); c.setFillColor(colors.HexColor('#003366'))
    c.drawString(120, height - 45, "KE BILLING PRO")
    c.setFont("Helvetica", 8); c.drawString(120, height - 55, "OFFICIAL DIGITAL INVOICE MANAGER")
    
    c.drawRightString(width - 40, height - 42, f"Account: {p.get('ke','---')}")
    c.drawRightString(width - 40, height - 52, f"Customer: {p.get('name','---')}")
    c.drawRightString(width - 40, height - 62, f"Billing Month: {b_month}")
    c.drawRightString(width - 40, height - 72, f"Issue Date: {curr_date}")

    # Summary Boxes
    def draw_box(x, y, w, h, title, amount, subtitle, color=colors.red):
        c.setStrokeColor(color); c.setLineWidth(1.2)
        c.roundRect(x, y, w, h, 12, stroke=1, fill=0)
        c.setFont("Helvetica-Bold", 9); c.setFillColor(colors.black)
        c.drawCentredString(x + w/2, y + h - 15, title)
        c.setFont("Helvetica-Bold", 16); c.drawCentredString(x + w/2, y + h/2 - 4, amount)
        c.setFont("Helvetica", 7); c.drawCentredString(x + w/2, y + 8, subtitle)

    grid_y = height - 160
    box_w = (width - 100) / 4
    draw_box(40, grid_y, box_w, 70, "Amount Due", f"Rs. {res_total:,.0f}", "Payable Now", colors.red)
    draw_box(50 + box_w, grid_y, box_w, 70, "Current Units", f"{units} kWh", "Total Consumption", colors.orange)
    draw_box(60 + box_w*2, grid_y, box_w, 70, "Previous Dues", "Rs. 0.00", "Remaining", colors.grey)
    draw_box(70 + box_w*3, grid_y, box_w, 70, "Due Date", curr_date, "Payment Deadline", colors.blue)

    # Breakdown Table
    y_sect = grid_y - 40
    c.setFont("Helvetica-Bold", 10); c.setFillColor(colors.HexColor('#003366'))
    c.drawString(40, y_sect, "Bill Breakdown")
    c.setFont("Helvetica", 8); c.setFillColor(colors.black)
    y_sect -= 20
    
    _, _, breakdown = calculate_bill(units, s)
    for b in breakdown:
        c.drawString(50, y_sect, f"{b['slab']} Unit * {b['units']} Unit Consume * {b['rate']} Charge")
        c.drawRightString(width-50, y_sect, f"Rs. {b['subtotal']:,.2f}")
        y_sect -= 12

    c.drawString(50, y_sect, "Fixed Charges")
    c.drawRightString(width-50, y_sect, f"Rs. {float(s.get('fixed_charge', 600)):,.2f}")
    y_sect -= 12
    c.drawString(50, y_sect, "Sales Tax")
    c.drawRightString(width-50, y_sect, f"Rs. {float(s.get('sales_tax', 350)):,.2f}")
    
    y_sect -= 20
    c.setFont("Helvetica-Bold", 11); c.setFillColor(colors.red)
    c.drawString(50, y_sect, "TOTAL PAYABLE")
    c.drawRightString(width-50, y_sect, f"Rs. {res_total:,.2f}")

    # --- Analytics Summary ---
    y_anal = y_sect - 40
    c.setLineWidth(0.5); c.setStrokeColor(colors.lightgrey)
    c.line(40, y_anal, width-40, y_anal)
    y_anal -= 20
    c.setFont("Helvetica-Bold", 11); c.setFillColor(colors.HexColor('#003366'))
    c.drawString(40, y_anal, "Analytics Summary")
    
    y_charts_top = y_anal - 40
    
    # 1. Pie Chart
    u_elec = res_total - float(s.get('fixed_charge', 600)) - float(s.get('sales_tax', 350))
    d1 = Drawing(160, 160)
    pc = Pie()
    pc.x = 25; pc.y = 25; pc.width = 110; pc.height = 110
    pc.data = [u_elec, float(s.get('sales_tax', 350)), float(s.get('fixed_charge', 600))]
    pc.labels = ['Energy', 'Tax', 'Fix']
    pc.sideLabels = 1
    pc.slices[0].fillColor = colors.HexColor('#003366')
    pc.slices[1].fillColor = colors.HexColor('#D32F2F')
    pc.slices[2].fillColor = colors.HexColor('#FFD700')
    d1.add(pc)
    d1.drawOn(c, 30, y_charts_top - 140)

    # 2. Bar Chart (Usage)
    history = p.get('history', [])
    h_units = [h['units'] for h in history[-6:]] if history else [0]
    h_months = [h['month'] for h in history[-6:]] if history else ['None']
    
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(width*0.72, y_charts_top, "Usage History (kWh)")
    d2 = Drawing(160, 160)
    bc = VerticalBarChart()
    bc.x = 35; bc.y = 40; bc.height = 85; bc.width = 120; bc.data = [h_units]
    bc.categoryAxis.categoryNames = h_months; bc.bars[0].fillColor = colors.HexColor('#003366')
    d2.add(bc); d2.drawOn(c, width/2 + 20, y_charts_top - 140)

    # 3. Line Chart (Revenue)
    h_totals = [h['total'] for h in history[-12:]] if history else [0]
    c.drawCentredString(width/2, y_charts_top - 160, "Revenue Trend (12 Months)")
    d3 = Drawing(width-100, 120)
    lp = LinePlot(); lp.x=40; lp.y=20; lp.height=80; lp.width=width-180; lp.data=[list(zip(range(len(h_totals)), h_totals))]
    lp.lines[0].strokeColor=colors.red; lp.lines[0].symbol=makeMarker('FilledCircle')
    d3.add(lp); d3.drawOn(c, 40, y_charts_top - 280)

    c.setFont("Helvetica-Oblique", 7); c.setFillColor(colors.grey)
    c.drawCentredString(width/2, 20, "Official KE Billing Pro Digital System")
    
    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

# --- Main App ---
def main():
    st.title("⚡ KE Billing Pro — Web Manager")
    
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False

    if not st.session_state.logged_in:
        col1, col2, col3 = st.columns([1,1,1])
        with col2:
            st.subheader("Login to your Account")
            user = st.text_input("Username")
            pin = st.text_input("Enter PIN", type="password")
            if st.button("LOGIN"):
                # Simplified check for demo
                st.session_state.logged_in = True
                st.session_state.username = user
                st.rerun()
        return

    # Data Persistence
    if 'profiles' not in st.session_state:
        # Load from file if exists, else init
        if os.path.exists('profiles.json'):
            with open('profiles.json', 'r') as f: st.session_state.profiles = json.load(f)
        else:
            st.session_state.profiles = {"Default": {"name": "Test Customer", "ke": "12345678", "prev": 0, "history": []}}

    # Sidebar
    st.sidebar.header("Management")
    prof_list = list(st.session_state.profiles.keys())
    sel_prof = st.sidebar.selectbox("Select Profile", prof_list)
    p = st.session_state.profiles[sel_prof]

    st.sidebar.divider()
    st.sidebar.subheader("Settings")
    fixed_chg = st.sidebar.number_input("Fixed Charges", value=DEFAULT_SETS['fixed_charge'])
    sales_tax = st.sidebar.number_input("Sales Tax", value=DEFAULT_SETS['sales_tax'])
    
    # Main Content
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("Billing Input")
        curr_reading = st.number_input("Current Meter Reading", value=p['prev'] + 100)
        bill_month = st.text_input("Billing Month", value=datetime.now().strftime("%B %Y"))
        
        units = curr_reading - p['prev']
        if units < 0:
            st.error("Current reading cannot be less than previous!")
            return
            
        total, cost, breakdown = calculate_bill(units, {'fixed_charge': fixed_chg, 'sales_tax': sales_tax})
        
        if st.button("CALCULATE & SAVE"):
            p['prev'] = curr_reading
            # Update history logic
            entry = {'month': bill_month[:6], 'total': total, 'units': units}
            if not any(h['month'] == entry['month'] for h in p['history']):
                p['history'].append(entry)
                p['history'] = p['history'][-12:]
            
            st.session_state.profiles[sel_prof] = p
            st.success("Bill updated and saved to history!")

    with col2:
        st.subheader("Summary")
        c1, c2 = st.columns(2)
        c1.metric("Total Payable", f"Rs. {total:,.2f}")
        c2.metric("Units Consumed", f"{units} kWh")
        
        st.info(f"Customer: {p['name']} | A/C: {p['ke']}")
        
        # WhatsApp Share
        msg = f"⚡ *KE BILLING PRO — INVOICE*\\n👤 *Customer:* {p['name']}\\n💵 *TOTAL DUE : Rs. {total:,.2f}*"
        wa_url = f"https://api.whatsapp.com/send?text={msg}"
        st.link_button("Share on WhatsApp", wa_url)
        
        # Download PDF
        pdf_data = generate_pdf({
            'profile': p, 'settings': {'fixed_charge': fixed_chg, 'sales_tax': sales_tax},
            'total': total, 'units': units, 'prev_reading': p['prev'] - units, 
            'curr_reading': curr_reading, 'month': bill_month
        })
        st.download_button("Download PDF Bill", data=pdf_data, file_name=f"Bill_{sel_prof}.pdf", mime="application/pdf")

    # History Table
    st.divider()
    st.subheader("Consumption History")
    if p['history']:
        st.table(p['history'])
        
        # Visuals
        st.subheader("Usage Trends")
        chart_data = {"Month": [h['month'] for h in p['history']], "Units": [h['units'] for h in p['history']]}
        st.bar_chart(chart_data, x="Month", y="Units")

if __name__ == "__main__":
    main()
