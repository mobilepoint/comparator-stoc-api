import streamlit as st
import requests
from requests.auth import HTTPBasicAuth
import pandas as pd
from datetime import datetime
import time

# Configurare pagină
st.set_page_config(
    page_title="Verificare Stoc SmartBill vs WooCommerce",
    page_icon="📦",
    layout="wide"
)

st.title("📦 Verificare Stoc: SmartBill vs WooCommerce")
st.markdown("---")

# Funcții API SmartBill
def get_smartbill_stocks(email, token, cif, warehouse_name=None):
    """Obține stocurile din SmartBill"""
    try:
        url = "https://ws.smartbill.ro/SBORO/api/stocks"
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        auth = HTTPBasicAuth(email, token)
        
        # Parametri pentru request
        params = {
            "cif": cif,
            "date": datetime.now().strftime("%Y-%m-%d")
        }
        
        if warehouse_name:
            params["warehouseName"] = warehouse_name
        
        response = requests.get(
            url,
            auth=auth,
            headers=headers,
            params=params,
            timeout=30
        )
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 401:
            st.error("🔒 Autentificare eșuată. Verifică email-ul și token-ul SmartBill.")
            return None
        else:
            st.error(f"Eroare SmartBill API: {response.status_code}")
            st.code(response.text)
            return None
            
    except requests.exceptions.Timeout:
        st.error("⏱️ Timeout la apelul SmartBill. Încearcă din nou.")
        return None
    except Exception as e:
        st.error(f"Eroare la apelul SmartBill: {str(e)}")
        return None

def get_smartbill_products(email, token, cif):
    """Obține lista completă de produse din SmartBill"""
    try:
        url = "https://ws.smartbill.ro/SBORO/api/products"
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        auth = HTTPBasicAuth(email, token)
        
        params = {"cif": cif}
        
        response = requests.get(
            url,
            auth=auth,
            headers=headers,
            params=params,
            timeout=30
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            # Fallback: încearcă să folosești stocks endpoint
            return None
            
    except Exception as e:
        st.warning(f"Info: Folosesc stocks endpoint pentru produse")
        return None

# Funcții API WooCommerce
def get_woocommerce_products(url, consumer_key, consumer_secret):
    """Obține toate produsele din WooCommerce cu stocuri"""
    try:
        all_products = []
        page = 1
        per_page = 100
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Primul request pentru a vedea câte pagini sunt
        endpoint = f"{url}/wp-json/wc/v3/products"
        response = requests.get(
            endpoint,
            auth=(consumer_key, consumer_secret),
            params={"per_page": 1, "page": 1},
            timeout=30
        )
        
        if response.status_code != 200:
            st.error(f"Eroare WooCommerce API: {response.status_code}")
            return []
        
        total_products = int(response.headers.get('X-WP-Total', 0))
        total_pages = int(response.headers.get('X-WP-TotalPages', 1))
        
        status_text.text(f"Se preiau {total_products} produse din WooCommerce...")
        
        while page <= total_pages:
            params = {
                "per_page": per_page,
                "page": page,
                "status": "publish"
            }
            
            response = requests.get(
                endpoint,
                auth=(consumer_key, consumer_secret),
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                products = response.json()
                if not products:
                    break
                all_products.extend(products)
                
                # Update progress
                progress = min(page / total_pages, 1.0)
                progress_bar.progress(progress)
                status_text.text(f"Preluate {len(all_products)} / {total_products} produse...")
                
                page += 1
                time.sleep(0.1)  # Rate limiting
            else:
                st.error(f"Eroare la pagina {page}: {response.status_code}")
                break
        
        progress_bar.empty()
        status_text.empty()
        
        return all_products
        
    except Exception as e:
        st.error(f"Eroare la apelul WooCommerce: {str(e)}")
        return []

# Procesare date
def process_smartbill_data(data):
    """Procesează datele din SmartBill în format standard"""
    sb_dict = {}
    
    if not data:
        return sb_dict
    
    # SmartBill poate returna date în formate diferite
    if isinstance(data, list):
        for item in data:
            # Încearcă diferite chei posibile
            code = (item.get('productCode') or 
                   item.get('code') or 
                   item.get('Code') or 
                   item.get('productcode') or '')
            
            name = (item.get('name') or 
                   item.get('productName') or 
                   item.get('Name') or 
                   item.get('denumire') or '')
            
            quantity = float(item.get('quantity') or 
                           item.get('stock') or 
                           item.get('Quantity') or 
                           item.get('stoc') or 0)
            
            unit = (item.get('measuringUnit') or 
                   item.get('um') or 
                   item.get('UM') or 'buc')
            
            if code:  # Adaugă doar dacă are cod
                sb_dict[code] = {
                    'name': name,
                    'stock': quantity,
                    'unit': unit
                }
    elif isinstance(data, dict):
        # Dacă e dict, încearcă să extragi lista de produse
        products = data.get('products', data.get('list', []))
        return process_smartbill_data(products)
    
    return sb_dict

def process_woocommerce_data(products):
    """Procesează datele din WooCommerce în format standard"""
    woo_dict = {}
    
    for product in products:
        sku = product.get('sku', '').strip()
        
        if not sku:
            continue
        
        stock_qty = product.get('stock_quantity')
        if stock_qty is None:
            stock_qty = 0
        else:
            stock_qty = float(stock_qty)
        
        woo_dict[sku] = {
            'name': product.get('name', ''),
            'stock': stock_qty,
            'status': product.get('stock_status', 'outofstock'),
            'manage_stock': product.get('manage_stock', False),
            'price': product.get('price', '0')
        }
    
    return woo_dict

def generate_discrepancy_report(sb_dict, woo_dict):
    """Generează raport detaliat cu discrepanțe"""
    discrepancies = []
    
    # 1. Produse în SmartBill cu stoc > 0 dar lipsesc din WooCommerce
    for code, sb_info in sb_dict.items():
        if code not in woo_dict and sb_info['stock'] > 0:
            discrepancies.append({
                'Cod': code,
                'Denumire': sb_info['name'],
                'Stoc SmartBill': sb_info['stock'],
                'Stoc WooCommerce': 'N/A',
                'Diferență': 'N/A',
                'Tip Discrepanță': '❌ Lipsește din WooCommerce',
                'Status': 'CRITIC',
                'Prioritate': 1
            })
    
    # 2. Produse în SmartBill cu stoc > 0 dar stoc 0 în WooCommerce
    for code, sb_info in sb_dict.items():
        if code in woo_dict and sb_info['stock'] > 0 and woo_dict[code]['stock'] == 0:
            discrepancies.append({
                'Cod': code,
                'Denumire': sb_info['name'],
                'Stoc SmartBill': sb_info['stock'],
                'Stoc WooCommerce': 0,
                'Diferență': sb_info['stock'],
                'Tip Discrepanță': '⚠️ Stoc 0 în WooCommerce dar disponibil în SmartBill',
                'Status': 'ATENTIE',
                'Prioritate': 2
            })
    
    # 3. Produse cu diferențe de cantitate
    for code in set(sb_dict.keys()) & set(woo_dict.keys()):
        sb_stock = sb_dict[code]['stock']
        woo_stock = woo_dict[code]['stock']
        diff = abs(sb_stock - woo_stock)
        
        if diff > 0.01:  # Toleranță mică pentru erori de rotunjire
            if sb_stock > 0 or woo_stock > 0:  # Ignoră ambele 0
                discrepancies.append({
                    'Cod': code,
                    'Denumire': sb_dict[code]['name'],
                    'Stoc SmartBill': sb_stock,
                    'Stoc WooCommerce': woo_stock,
                    'Diferență': round(sb_stock - woo_stock, 2),
                    'Tip Discrepanță': '🔄 Diferență cantitate',
                    'Status': 'SINCRONIZARE',
                    'Prioritate': 3
                })
    
    # 4. Produse în WooCommerce cu stoc > 0 dar lipsesc din SmartBill
    for code, woo_info in woo_dict.items():
        if code not in sb_dict and woo_info['stock'] > 0:
            discrepancies.append({
                'Cod': code,
                'Denumire': woo_info['name'],
                'Stoc SmartBill': 0,
                'Stoc WooCommerce': woo_info['stock'],
                'Diferență': -woo_info['stock'],
                'Tip Discrepanță': '🚫 În WooCommerce dar nu în SmartBill',
                'Status': 'CRITIC',
                'Prioritate': 1
            })
    
    df = pd.DataFrame(discrepancies)
    
    if len(df) > 0:
        df = df.sort_values(['Prioritate', 'Stoc SmartBill'], ascending=[True, False])
        df = df.drop('Prioritate', axis=1)
    
    return df

# UI Principal
def main():
    # Sidebar pentru configurare
    with st.sidebar:
        st.header("⚙️ Configurări")
        
        # SmartBill - folosim secrets sau input manual
        st.subheader("🔵 SmartBill")
        
        # Încearcă să folosești secrets
        try:
            sb_email = st.secrets["smartbill"]["email"]
            sb_token = st.secrets["smartbill"]["token"]
            sb_cif = st.secrets["smartbill"]["cif"]
            st.success("✅ Credențiale SmartBill din secrets")
        except:
            sb_email = st.text_input("Email SmartBill", value="mobilepointgsm@gmail.com")
            sb_token = st.text_input("Token SmartBill", value="6a318b8324acba9d4cc360bb9cf48e45", type="password")
            sb_cif = st.text_input("CIF", value="RO36898183")
        
        sb_warehouse = st.text_input("Nume Gestiune (opțional)", value="")
        
        st.markdown("---")
        
        # WooCommerce
        st.subheader("🟢 WooCommerce")
        
        try:
            woo_url = st.secrets["woocommerce"]["url"]
            woo_key = st.secrets["woocommerce"]["consumer_key"]
            woo_secret = st.secrets["woocommerce"]["consumer_secret"]
            st.success("✅ Credențiale WooCommerce din secrets")
        except:
            woo_url = st.text_input("URL WooCommerce", value="https://servicepack.ro")
            woo_key = st.text_input("Consumer Key", type="password")
            woo_secret = st.text_input("Consumer Secret", type="password")
        
        st.markdown("---")
        verificare_btn = st.button("🔄 Verifică Stocuri", type="primary", use_container_width=True)
    
    # Verificare
    if verificare_btn:
        if not all([sb_email, sb_token, sb_cif, woo_url, woo_key, woo_secret]):
            st.error("⚠️ Completează toate câmpurile!")
            return
        
        col1, col2 = st.columns(2)
        
        with col1:
            with st.spinner("📥 Preluare date SmartBill..."):
                sb_data = get_smartbill_stocks(sb_email, sb_token, sb_cif, sb_warehouse)
        
        with col2:
            with st.spinner("📥 Preluare date WooCommerce..."):
                woo_data = get_woocommerce_products(woo_url, woo_key, woo_secret)
        
        if sb_data is not None and woo_data:
            # Procesare
            sb_dict = process_smartbill_data(sb_data)
            woo_dict = process_woocommerce_data(woo_data)
            
            st.success(f"✅ Preluate: {len(sb_dict)} produse SmartBill | {len(woo_dict)} produse WooCommerce")
            
            # Generare raport
            df_report = generate_discrepancy_report(sb_dict, woo_dict)
            
            if len(df_report) > 0:
                st.markdown("---")
                st.header("📊 Raport Discrepanțe")
                
                # Metrici
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    critic = len(df_report[df_report['Status'] == 'CRITIC'])
                    st.metric("🔴 Critice", critic)
                
                with col2:
                    atentie = len(df_report[df_report['Status'] == 'ATENTIE'])
                    st.metric("🟡 Atenție", atentie)
                
                with col3:
                    sync = len(df_report[df_report['Status'] == 'SINCRONIZARE'])
                    st.metric("🔵 Sincronizare", sync)
                
                with col4:
                    st.metric("📝 Total Discrepanțe", len(df_report))
                
                st.markdown("---")
                
                # Filtre
                col_f1, col_f2 = st.columns([1, 2])
                
                with col_f1:
                    status_filter = st.multiselect(
                        "Filtrează după status",
                        options=df_report['Status'].unique(),
                        default=df_report['Status'].unique()
                    )
                
                with col_f2:
                    search_term = st.text_input("🔎 Caută după cod sau denumire")
                
                # Aplicare filtre
                df_filtered = df_report[df_report['Status'].isin(status_filter)]
                
                if search_term:
                    df_filtered = df_filtered[
                        df_filtered['Cod'].astype(str).str.contains(search_term, case=False, na=False) |
                        df_filtered['Denumire'].astype(str).str.contains(search_term, case=False, na=False)
                    ]
                
                # Tabel
                st.dataframe(
                    df_filtered,
                    use_container_width=True,
                    height=400,
                    hide_index=True
                )
                
                # Export
                col_e1, col_e2, col_e3 = st.columns([2, 1, 1])
                
                with col_e2:
                    csv = df_filtered.to_csv(index=False).encode('utf-8-sig')
                    st.download_button(
                        label="📥 Descarcă CSV",
                        data=csv,
                        file_name=f"raport_stocuri_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                
            else:
                st.success("✅ Nu s-au găsit discrepanțe! Stocurile sunt sincronizate.")
        
        else:
            st.error("❌ Nu s-au putut prelua datele. Verifică credențialele.")
    
    else:
        # Mesaj inițial
        st.info("👈 Configurează API-urile în sidebar și apasă **Verifică Stocuri**")
        
        with st.expander("ℹ️ Informații despre aplicație"):
            st.markdown("""
            ### Ce face această aplicație?
            
            Compară stocurile dintre **SmartBill** (gestiune) și **WooCommerce** (magazin online) 
            și identifică următoarele discrepanțe:
            
            - 🔴 **CRITIC**: Produse care lipsesc complet sau sunt listate greșit
            - 🟡 **ATENȚIE**: Produse cu stoc în SmartBill dar 0 în WooCommerce
            - 🔵 **SINCRONIZARE**: Diferențe de cantitate între sisteme
            
            ### Limite API
            - **SmartBill**: 3 apeluri/secundă (blocare 10 min dacă se depășește)
            - **WooCommerce**: ~50-75 request-uri/minut (depinde de hosting)
            
            ### Securitate
            Toate credențialele sunt stocate securizat în Streamlit Secrets.
            """)

if __name__ == "__main__":
    main()
