Python

import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta

# Configurazione della pagina
st.set_page_config(
    page_title="Sorare Opta Lineup Optimizer (IOSO)",
    page_icon="⚽",
    layout="wide"
)

st.title("⚽ Sorare Lineup Optimizer & Opta Match-up Analyzer")
st.markdown("Sistema di scouting e gestione formazioni ibrido (Sorare API + Metriche Opta + Calendari).")

# --- BARRA LATERALE: PARAMETRI IOSO ---
st.sidebar.header("⚙️ Pesi Indice IOSO")
user_slug = st.sidebar.text_input("Username Sorare", value="lenders09")
peso_duelli = st.sidebar.slider("Peso Differenziale Duelli", 0.1, 2.0, 0.8)
peso_passaggi = st.sidebar.slider("Peso Precisione Passaggi", 0.1, 1.0, 0.4)
peso_xg_xa = st.sidebar.slider("Peso Expected Goals/Assists (xG+xA)", 1.0, 20.0, 12.0)

# --- FUNZIONE API DI RECUPERO GALLERIA ---
def carica_galleria_sorare(slug):
    url_sorare = "https://api.sorare.com/graphql"
    query = """
    {
      user(slug: "%s") {
        nickname
        cards(first: 50) {
          nodes {
            id
            rarityTyped
            ... on Card {
              player {
                displayName
                position
                activeClub { name }
                country { name code }
              }
            }
          }
        }
      }
    }
    """ % slug
    
    mappa_ruoli = {
        "goalkeeper": "Portiere",
        "defender": "Difensore",
        "midfielder": "Centrocampista",
        "forward": "Attaccante"
    }
    
    try:
        # Timeout di 5 secondi per evitare che l'app si blocchi all'infinito
        response = requests.post(url_sorare, json={'query': query}, timeout=5)
        risposta_sorare = response.json()
        
        giocatori_estratti = []
        if "data" in risposta_sorare and risposta_sorare["data"]["user"]:
            carte = risposta_sorare["data"]["user"]["cards"]["nodes"]
            for c in carte:
                p = c.get('player')
                if p and 'displayName' in p:
                    nome = p['displayName']
                    club_obj = p.get('activeClub', {})
                    club_nome = club_obj.get('name', 'Club Sconosciuto') if club_obj else 'Club Sconosciuto'
                    country_obj = p.get('country', {})
                    nazione_nome = country_obj.get('name', 'Nazionale') if country_obj else 'Nazionale'
                    
                    rarita = c.get('rarityTyped', 'N/D')
                    pos_inglese = p.get('position', '').lower()
                    ruolo_italiano = mappa_ruoli.get(pos_inglese, "Sconosciuto")
                    
                    if ruolo_italiano != "Sconosciuto":
                        giocatori_estratti.append({
                            "Giocatore": nome,
                            "Ruolo": ruolo_italiano,
                            "Club": club_nome,
                            "Nazione Nome": nazione_nome,
                            "Rarità": rarita
                        })
        return pd.DataFrame(giocatori_estratti)
    except Exception:
        return pd.DataFrame()

# --- PULSANTE DI SINCRONIZZAZIONE ---
st.markdown("---")
col_sync1, col_sync2 = st.columns([3, 1])
with col_sync1:
    st.info("🔄 Clicca su **Sincronizza Galleria** per scaricare i dati da Sorare ed elaborare la formazione.")
with col_sync2:
    sincronizza_btn = st.button("🔄 Sincronizza Galleria", use_container_width=True)

# Gestione stato della sessione per non bloccare il caricamento iniziale
if "df_mercato" not in st.session_state:
    st.session_state["df_mercato"] = pd.DataFrame()

if sincronizza_btn:
    with st.spinner("Connessione a Sorare in corso..."):
        st.session_state["df_mercato"] = carica_galleria_sorare(user_slug)

df_mercato = st.session_state["df_mercato"]

if df_mercato.empty:
    st.warning("⚠️ La galleria è vuota o non ancora sincronizzata. Premi il pulsante **Sincronizza Galleria** in alto per iniziare.")
else:
    st.success(f"✅ Galleria caricata! Trovate **{len(df_mercato)} carte** attive.")

    # --- SIMULAZIONE CALENDARIO E AVVERSARI ---
    oggi = datetime.now()
    date_calendario = [(oggi + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(5)]
    
    dati_analizzati = []
    for index, row in df_mercato.iterrows():
        data_match = date_calendario[index % len(date_calendario)]
        
        if index % 2 == 0:
            contesto = "Nazionale (Sosta)"
            avversario = f"Nazionale Avversaria ({row['Nazione Nome']} vs Selezione avversaria)"
        else:
            contesto = "Campionato / Club"
            avversario = f"Club avversario ({row['Club']} vs Club avversario)"
        
        media_sorare_base = round(45.0 + (index * 1.5) % 30, 1)
        duelli_vinti = 8 + (index * 2) % 10
        duelli_persi = 3 + index % 5
        differenziale_duelli = duelli_vinti - duelli_persi
        precisione_passaggi = round(80.0 + (index * 1.2) % 14, 1)
        xg_xa = round(0.2 + (index * 0.1) % 0.6, 2)
        difficolta_avversario = 1.05 if "Nazionale" in contesto else 1.0
        
        ios_score = (
            media_sorare_base 
            + (differenziale_duelli * peso_duelli) 
            + ((precisione_passaggi - 75) * peso_passaggi) 
            + (xg_xa * peso_xg_xa)
        ) / difficolta_avversario
        
        ios_score = round(ios_score, 1)
        if ios_score > 100: ios_score = 100.0
        
        dati_analizzati.append({
            "Giocatore": row["Giocatore"],
            "Ruolo": row["Ruolo"],
            "Club": row["Club"],
            "Squadra/Nazione in Campo": row['Nazione Nome'] if "Nazionale" in contesto else row['Club'],
            "Contesto Impegno": contesto,
            "Avversario": avversario,
            "Data Partita": data_match,
            "Media Sorare": media_sorare_base,
            "Diff. Duelli": differenziale_duelli,
            "Passaggi %": precisione_passaggi,
            "xG+xA": xg_xa,
            "IOSO (Indice Ottimizzato)": ios_score
        })

    df_completo = pd.DataFrame(dati_analizzati)

    # --- SELETTORE DATA ---
    st.markdown("---")
    st.subheader("📅 Selettore Data e Turno di Game Week")
    
    date_disponibili = sorted(df_completo["Data Partita"].unique())
    data_selezionata = st.selectbox("Seleziona la data:", date_disponibili)
    df_filtrato_data = df_completo[df_completo["Data Partita"] == data_selezionata].copy()

    st.write(f"In data **{data_selezionata}** risultano impegnati **{len(df_filtrato_data)} giocatori**.")

    with st.expander("🔍 Mostra dettagli giocatori in questa data"):
        st.dataframe(df_filtrato_data[[
            "Giocatore", "Ruolo", "Contesto Impegno", "Squadra/Nazione in Campo", 
            "Avversario", "Media Sorare", "IOSO (Indice Ottimizzato)"
        ]], use_container_width=True)

    # --- FORMAZIONE A 5 ---
    st.markdown("---")
    st.subheader(f"🏆 Formazione Ideale a 5 Elementi ({data_selezionata})")

    formazione_ideale = []
    ruoli_obbligatori = ["Portiere", "Difensore", "Centrocampista", "Attaccante"]
    df_lavoro = df_filtrato_data.copy()
    
    for r in ruoli_obbligatori:
        subset_ruolo = df_lavoro[df_lavoro["Ruolo"] == r]
        if not subset_ruolo.empty:
            migliore = subset_ruolo.loc[subset_ruolo["IOSO (Indice Ottimizzato)"].idxmax()]
            formazione_ideale.append(migliore.to_dict())
            df_lavoro = df_lavoro[df_lavoro["Giocatore"] != migliore["Giocatore"]]

    df_solo_movimento = df_lavoro[df_lavoro["Ruolo"] != "Portiere"]
    if not df_solo_movimento.empty:
        extra = df_solo_movimento.loc[df_solo_movimento["IOSO (Indice Ottimizzato)"].idxmax()]
        extra_dict = extra.to_dict()
        extra_dict["Ruolo"] = f"Extra ({extra_dict['Ruolo']})"
        formazione_ideale.append(extra_dict)

    if formazione_ideale:
        df_formazione = pd.DataFrame(formazione_ideale)
        st.dataframe(df_formazione[[
            "Ruolo", "Giocatore", "Contesto Impegno", "Squadra/Nazione in Campo", 
            "Avversario", "Media Sorare", "Diff. Duelli", "Passaggi %", "xG+xA", "IOSO (Indice Ottimizzato)"
        ]], use_container_width=True)
        
        totale_ios = df_formazione["IOSO (Indice Ottimizzato)"].sum()
        st.success(f"🎯 **Indice IOSO Totale:** {totale_ios:.1f} / 500.0")
