"""
Aplicație Streamlit optimizată - CORECTAT pentru schema catalog
"""

import streamlit as st
import requests
from requests.auth import HTTPBasicAuth
import pandas as pd
from datetime import datetime
from supabase import create_client, Client
import time
import io

# ====================== CONFIGURARE ======================

st.set_page_config(
    page_title="Verificare Stoc SmartBill vs WooCommerce",
    page_icon="📦",
    layout="wide"
)

WAREHOUSE_NAME = "Eroilor 19 cv"
WAREHOUSE_TYPE = "en gros"

# ====================== SIDEBAR ======================

with st.sidebar:
    st.header("⚙️ Configurări")
    
    st.subheader("🔵 SmartBill")
    try:
        sb_email = st.secrets["smartbill"]["email"]
        sb_token = st.secrets["smartbill"]["token"]
        sb_cif = st.secrets["smartbill"]["cif"]
        st.success("✅ SmartBill")
    except:
        sb_email = st.text_input("Email SmartBill", value="mobilepointgsm@gmail.com")
        sb_token = st.text_input("Token SmartBill", type="password")
        sb_cif = st.text_input("CIF", value="RO36898183")
    
    st.info(f"**Gestiune**: {WAREHOUSE_NAME}\n**Tip**: {WAREHOUSE_TYPE}")
    st.markdown("---")
    
    st.subheader("🟢 WooCommerce")
    try:
        woo_url = st.secrets["woocommerce"]["url"]
        woo_key = st.secrets["woocommerce"]["consumer_key"]
        woo_secret = st.secrets["woocommerce"]["consumer_secret"]
        st.success("✅ WooCommerce")
    except:
        woo_url = st.text_input("URL WooCommerce", value="https://servicepack.ro")
        woo_key = st.text_input("Consumer Key", type="password")
        woo_secret = st.text_input("Consumer Secret", type="password")
    
    st.markdown("---")
    
    st.subheader("💾 Supabase")
    try:
        supabase_url = st.secrets["supabase"]["url"]
        supabase_key = st.secrets["supabase"]["key"]
        supabase: Client = create_client(supabase_url, supabase_key)
        st.success("✅ Conectat")
    except:
        supabase_url = st.text_input("Supabase URL")
        supabase_key = st.text_input("Supabase Key", type="password")
        if supabase_url and supabase_key:
            try:
                supabase = create_client(supabase_url, supabase_key)
                st.success("✅ Conectat")
            except:
                st.error("❌ Eroare")
                supabase = None
        else:
            supabase = None

# ====================== FUNCȚII UPDATE RAPID ======================

def update_stocks_only(woo_url, woo_key, woo_secret, supabase_client):
    """Update RAPID stocuri"""
    
    st.markdown("---")
    st.subheader("⚡ Update Rapid Stocuri")
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # CORECTAT: Folosește schema catalog
    status_text.text("📥 Citire SKU-uri din Supabase...")
    
    try:
        result = supabase_client.schema('catalog').table('woocommerce_stock').select('sku, woo_product_id').execute()
        existing_products = {row['sku']: row.get('woo_product_id') for row in result.data}
        st.info(f"📦 {len(existing_products)} SKU-uri în Supabase")
    except Exception as e:
        st.error(f"Eroare: {e}")
        return False
    
    progress_bar.progress(0.2)
    
    status_text.text("📥 Preluare stocuri WooCommerce...")
    
    stock_updates = []
    page = 1
    per_page = 100
    endpoint = f"{woo_url}/wp-json/wc/v3/products"
    
    while True:
        try:
            response = requests.get(
                endpoint,
                auth=(woo_key, woo_secret),
                params={
                    "per_page": per_page,
                    "page": page,
                    "status": "publish",
                    "_fields": "id,sku,stock_quantity,stock_status,type"
                },
                timeout=30
            )
            
            if response.status_code != 200:
                break
            
            products = response.json()
            if not products:
                break
            
            for p in products:
                sku = p.get('sku', '').strip()
                if sku and sku in existing_products:
                    stock_qty = float(p.get('stock_quantity') or 0)
                    
                    stock_updates.append({
                        'sku': sku,
                        'stock_quantity': stock_qty,
                        'stock_status': p.get('stock_status', 'outofstock'),
                        'last_synced_at': datetime.now().isoformat()
                    })
            
            status_text.text(f"📥 Stocuri: {len(stock_updates)}...")
            page += 1
            time.sleep(0.1)
            
        except Exception as e:
            st.error(f"Eroare: {e}")
            break
    
    progress_bar.progress(0.8)
    
    if stock_updates:
        status_text.text(f"💾 Actualizare {len(stock_updates)} stocuri...")
        
        updated = 0
        batch_size = 500
        
        for i in range(0, len(stock_updates), batch_size):
            batch = stock_updates[i:i+batch_size]
            
            try:
                # CORECTAT: Schema catalog
                supabase_client.schema('catalog').table('woocommerce_stock').upsert(batch).execute()
                updated += len(batch)
            except Exception as e:
                st.error(f"Eroare batch {i//batch_size + 1}: {e}")
        
        progress_bar.progress(1.0)
        status_text.empty()
        progress_bar.empty()
        
        st.success(f"✅ Actualizate {updated} stocuri")
        return True
    else:
        st.warning("⚠️ Nu s-au găsit stocuri")
        return False

# ====================== FUNCȚIE SYNC COMPLET ======================

def sync_woocommerce_full(woo_url, woo_key, woo_secret, supabase_client):
    """Sincronizare COMPLETĂ"""
    
    st.markdown("---")
    st.subheader("🔄 Sincronizare COMPLETĂ")
    st.warning("⚠️ Poate dura 20-30 minute")
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    status_text.text("📥 Preluare produse...")
    
    all_items = []
    page = 1
    per_page = 100
    endpoint = f"{woo_url}/wp-json/wc/v3/products"
    
    products_data = []
    while True:
        try:
            response = requests.get(
                endpoint,
                auth=(woo_key, woo_secret),
                params={"per_page": per_page, "page": page, "status": "publish"},
                timeout=30
            )
            
            if response.status_code != 200:
                break
            
            products = response.json()
            if not products:
                break
            
            products_data.extend(products)
            status_text.text(f"📥 Pagina {page}: {len(products_data)}...")
            page += 1
            time.sleep(0.1)
            
        except Exception as e:
            st.error(f"Eroare: {e}")
            break
    
    progress_bar.progress(0.3)
    
    simple_products = [p for p in products_data if p.get('type') in ['simple', 'external', 'grouped']]
    variable_products = [p for p in products_data if p.get('type') == 'variable']
    
    st.info(f"📦 Simple: {len(simple_products)} | Variabile: {len(variable_products)}")
    all_items.extend(simple_products)
    
    if variable_products:
        status_text.text(f"🔄 Preluare variații...")
        total_variations = 0
        
        for idx, var_product in enumerate(variable_products, 1):
            product_id = var_product['id']
            var_page = 1
            
            while True:
                try:
                    var_endpoint = f"{woo_url}/wp-json/wc/v3/products/{product_id}/variations"
                    var_response = requests.get(
                        var_endpoint,
                        auth=(woo_key, woo_secret),
                        params={"per_page": 100, "page": var_page},
                        timeout=30
                    )
                    
                    if var_response.status_code != 200:
                        break
                    
                    variations = var_response.json()
                    if not variations:
                        break
                    
                    all_items.extend(variations)
                    total_variations += len(variations)
                    var_page += 1
                    time.sleep(0.05)
                    
                except:
                    break
            
            if idx % 20 == 0 or idx == len(variable_products):
                status_text.text(f"🔄 {idx}/{len(variable_products)} ({total_variations} variații)")
                progress_bar.progress(0.3 + (0.4 * (idx / len(variable_products))))
    
    progress_bar.progress(0.7)
    st.success(f"✅ Total: {len(all_items)} produse")
    
    status_text.text("💾 Procesare...")
    
    stock_data = []
    new_products = []
    
    for product in all_items:
        sku = product.get('sku', '').strip()
        if not sku:
            continue
        
        stock_data.append({
            'sku': sku,
            'stock_quantity': float(product.get('stock_quantity') or 0),
            'stock_status': product.get('stock_status', 'outofstock'),
            'product_type': product.get('type', 'unknown'),
            'woo_product_id': product.get('id', 0),
            'last_synced_at': datetime.now().isoformat()
        })
        
        new_products.append({
            'sku': sku,
            'name': product.get('name', ''),
            'name_norm': product.get('name', '').lower().strip()
        })
    
    progress_bar.progress(0.8)
    
    # CORECTAT: Schema catalog pentru product_sku
    try:
        result = supabase_client.schema('catalog').table('product_sku').select('sku').execute()
        existing_skus = {row['sku'] for row in result.data}
    except:
        existing_skus = set()
    
    truly_new = [p for p in new_products if p['sku'] not in existing_skus]
    
    if truly_new:
        status_text.text(f"📝 Inserare {len(truly_new)} produse noi...")
        inserted = 0
        
        for i in range(0, len(truly_new), 50):
            batch = truly_new[i:i+50]
            try:
                product_data = [{'name': p['name'], 'name_norm': p['name_norm']} for p in batch]
                # CORECTAT: Schema catalog pentru product
                result = supabase_client.schema('catalog').table('product').insert(product_data).execute()
                
                if result.data:
                    for idx, row in enumerate(result.data):
                        try:
                            # CORECTAT: Schema catalog pentru product_sku
                            supabase_client.schema('catalog').table('product_sku').insert({
                                'product_id': row['id'],
                                'sku': batch[idx]['sku'],
                                'is_primary': True
                            }).execute()
                            inserted += 1
                        except:
                            pass
            except Exception as e:
                st.error(f"Eroare produse noi: {e}")
        
        st.success(f"✅ Inserate {inserted} produse")
    
    progress_bar.progress(0.9)
    
    status_text.text(f"💾 Actualizare {len(stock_data)} stocuri...")
    upserted = 0
    
    for i in range(0, len(stock_data), 500):
        batch = stock_data[i:i+500]
        try:
            # CORECTAT: Schema catalog pentru woocommerce_stock
            supabase_client.schema('catalog').table('woocommerce_stock').upsert(batch).execute()
            upserted += len(batch)
        except Exception as e:
            st.error(f"Eroare batch {i//500 + 1}: {e}")
    
    progress_bar.progress(1.0)
    status_text.empty()
    progress_bar.empty()
    
    st.success(f"✅ Sincronizare completă! {upserted} stocuri")
    return True

# ====================== FUNCȚII RAPORTARE ======================

def get_woocommerce_stock_from_supabase(supabase_client):
    """Citește stocuri din Supabase"""
    try:
        # CORECTAT: Schema catalog
        result = supabase_client.schema('catalog').table('woocommerce_stock').select('*').execute()
        
        woo_dict = {}
        for row in result.data:
            woo_dict[row['sku']] = {
                'stock': float(row.get('stock_quantity', 0)),
                'status': row.get('stock_status', 'outofstock'),
                'type': row.get('product_type', 'unknown')
            }
        
        return woo_dict
    except Exception as e:
        st.error(f"Eroare: {e}")
        return {}

def get_smartbill_stocks(email, token, cif, warehouse_name):
    """Preia stocuri SmartBill"""
    try:
        url = "https://ws.smartbill.ro/SBORO/api/stocks"
        
        response = requests.get(
            url,
            auth=HTTPBasicAuth(email, token),
            headers={"Content-Type": "application/xml", "Accept": "application/json"},
            params={"cif": cif, "date": datetime.now().strftime("%Y-%m-%d"), "warehouseName": warehouse_name},
            timeout=30
        )
        
        return response.json() if response.status_code == 200 else None
    except:
        return None

def process_smartbill_data(data):
    """Procesează SmartBill"""
    sb_dict = {}
    if not data:
        return sb_dict
    
    products = []
    if isinstance(data, dict) and "list" in data:
        for w in data["list"]:
            if isinstance(w, dict) and "products" in w:
                products.extend(w["products"])
    
    for p in products:
        if not isinstance(p, dict):
            continue
        code = p.get('productCode', '').strip()
        if code:
            sb_dict[code] = {
                'name': p.get('productName', ''),
                'stock': float(p.get('quantity', 0))
            }
    
    return sb_dict

def generate_discrepancy_report(sb_dict, woo_dict):
    """Generează raport"""
    disc = []
    
    for code, sb in sb_dict.items():
        if code not in woo_dict and sb['stock'] > 0:
            disc.append({
                'SKU': code, 'Denumire': sb['name'],
                'Stoc SmartBill': sb['stock'], 'Stoc WooCommerce': 'N/A',
                'Diferență': sb['stock'], 'Tip': '❌ Lipsește din Woo', 'Status': 'CRITIC', 'P': 1
            })
        elif code in woo_dict and sb['stock'] > 0 and woo_dict[code]['stock'] == 0:
            disc.append({
                'SKU': code, 'Denumire': sb['name'],
                'Stoc SmartBill': sb['stock'], 'Stoc WooCommerce': 0,
                'Diferență': sb['stock'], 'Tip': '⚠️ Stoc 0 în Woo', 'Status': 'ATENTIE', 'P': 2
            })
    
    for code in set(sb_dict.keys()) & set(woo_dict.keys()):
        diff = sb_dict[code]['stock'] - woo_dict[code]['stock']
        if abs(diff) > 0.01:
            disc.append({
                'SKU': code, 'Denumire': sb_dict[code]['name'],
                'Stoc SmartBill': sb_dict[code]['stock'], 'Stoc WooCommerce': woo_dict[code]['stock'],
                'Diferență': round(diff, 2), 'Tip': '🔄 Diferență', 'Status': 'SINCRONIZARE', 'P': 3
            })
    
    for code, woo in woo_dict.items():
        if code not in sb_dict and woo['stock'] > 0:
            disc.append({
                'SKU': code, 'Denumire': 'N/A',
                'Stoc SmartBill': 0, 'Stoc WooCommerce': woo['stock'],
                'Diferență': -woo['stock'], 'Tip': '🚫 În Woo nu în SB', 'Status': 'CRITIC', 'P': 1
            })
    
    df = pd.DataFrame(disc)
    if len(df) > 0:
        df = df.sort_values(['P', 'Stoc SmartBill'], ascending=[True, False]).drop('P', axis=1)
    return df

def create_excel_report(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Discrepante', index=False)
    return output.getvalue()

# ====================== UI PRINCIPAL ======================

st.title("📦 Verificare Stoc: SmartBill vs WooCommerce")
st.markdown("---")

# Info
if supabase:
    try:
        # CORECTAT: Schema catalog
        result = supabase.schema('catalog').table('woocommerce_stock').select('last_synced_at').order('last_synced_at', desc=True).limit(1).execute()
        if result.data:
            st.info(f"📅 Ultima sincronizare: {result.data[0]['last_synced_at']}")
    except:
        pass

st.markdown("---")

# Butoane
col1, col2, col3 = st.columns([1, 1, 1])

with col1:
    quick_update = st.button("⚡ Update Rapid", type="primary", use_container_width=True, help="~2 min")

with col2:
    full_sync = st.button("🔄 Sync Complet", type="secondary", use_container_width=True, help="~30 min")

with col3:
    report_btn = st.button("📊 Raport", type="secondary", use_container_width=True)

# LOGICA
if quick_update:
    if not supabase or not all([woo_url, woo_key, woo_secret]):
        st.error("⚠️ Configurează credențialele!")
    else:
        update_stocks_only(woo_url, woo_key, woo_secret, supabase)

if full_sync:
    if not supabase or not all([woo_url, woo_key, woo_secret]):
        st.error("⚠️ Configurează credențialele!")
    else:
        sync_woocommerce_full(woo_url, woo_key, woo_secret, supabase)

if report_btn:
    if not supabase or not all([sb_email, sb_token, sb_cif]):
        st.error("⚠️ Configurează credențialele!")
    else:
        st.markdown("---")
        st.subheader("📊 Raport")
        
        with st.spinner("📥 Preluare..."):
            woo_dict = get_woocommerce_stock_from_supabase(supabase)
            sb_data = get_smartbill_stocks(sb_email, sb_token, sb_cif, WAREHOUSE_NAME)
        
        if woo_dict and sb_data:
            sb_dict = process_smartbill_data(sb_data)
            st.success(f"✅ Woo: {len(woo_dict)} | SB: {len(sb_dict)}")
            
            df = generate_discrepancy_report(sb_dict, woo_dict)
            
            if len(df) > 0:
                st.header("📊 Discrepanțe")
                
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("🔴 Critice", len(df[df['Status'] == 'CRITIC']))
                m2.metric("🟡 Atenție", len(df[df['Status'] == 'ATENTIE']))
                m3.metric("🔵 Sincronizare", len(df[df['Status'] == 'SINCRONIZARE']))
                m4.metric("📝 Total", len(df))
                
                st.markdown("---")
                
                f1, f2 = st.columns([1, 2])
                with f1:
                    status_filter = st.multiselect("Status", df['Status'].unique(), df['Status'].unique())
                with f2:
                    search = st.text_input("🔎 Caută")
                
                df_filt = df[df['Status'].isin(status_filter)]
                if search:
                    df_filt = df_filt[
                        df_filt['SKU'].astype(str).str.contains(search, case=False, na=False) |
                        df_filt['Denumire'].astype(str).str.contains(search, case=False, na=False)
                    ]
                
                st.dataframe(df_filt, use_container_width=True, height=450, hide_index=True)
                
                e1, e2, e3 = st.columns([2, 1, 1])
                with e2:
                    csv = df_filt.to_csv(index=False).encode('utf-8-sig')
                    st.download_button("📥 CSV", csv, f"raport_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", use_container_width=True)
                with e3:
                    try:
                        excel = create_excel_report(df_filt)
                        st.download_button("📊 Excel", excel, f"raport_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx", use_container_width=True)
                    except:
                        pass
            else:
                st.success("🎉 Nu există discrepanțe!")
                st.balloons()
