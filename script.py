import json
import os
import requests

# 1. Endpoint officiel APIDAE v002 pour les listes
API_URL = "https://api.apidae-tourisme.com/api/v002/recherche/list-objets-touristiques"
API_KEY = os.environ.get("APIDAE_KEY")
PROJECT_ID = os.environ.get("APIDAE_PROJECT_ID")

# 2. Vos 6 sélections d'hébergements (Remplacez les numéros par vos vrais ID Apidae)
CATEGORIES = {
    "hotels": {"id_selection": 111111, "features": []},
    "campings": {"id_selection": 222222, "features": []},
    "chambres_hotes": {"id_selection": 333333, "features": []},
    "gites_etape": {"id_selection": 444444, "features": []},
    "refuges": {"id_selection": 555555, "features": []},
    "villages_vacances": {"id_selection": 666666, "features": []}
}

def clean_html(text):
    if not text: return ""
    return text.replace("<br>", "\n").replace("<br/>", "\n")

def get_adresse(obj):
    """Extraction exacte de l'adresse imbriquée en Apidae V002."""
    localisation = obj.get("localisation", {})
    adresse_obj = localisation.get("adresse", {})
    
    lignes = adresse_obj.get("adresse1", "")
    if adresse_obj.get("adresse2"):
        lignes += f", {adresse_obj.get('adresse2')}"
        
    code_postal = adresse_obj.get("codePostal", "")
    commune_data = adresse_obj.get("commune", "")
    commune = commune_data.get("nom", "") if isinstance(commune_data, dict) else commune_data
    
    return f"{lignes} {code_postal} {commune}".strip()

def extract_contacts(obj):
    tel, email, web = "", "", ""
    communications = obj.get("informations", {}).get("moyensCommunication", [])
    for contact in communications:
        type_com = contact.get("type", {}).get("id")
        valeur = contact.get("coordonnees", {}).get("fr", "")
        if type_com == 201 and not tel: tel = valeur     
        elif type_com == 204 and not email: email = valeur 
        elif type_com == 205 and not web: web = valeur   
    return tel, email, web

def extract_photo(obj):
    """Extraction exacte de l'URL de l'image dans le sous-tableau traductionFichiers."""
    illustrations = obj.get("illustrations", [])
    if illustrations and len(illustrations) > 0:
        first_illus = illustrations[0] # Premier dictionnaire d'illustration
        
        # En V002, traductionFichiers est TOUJOURS une liste [0]
        trad_fichiers = first_illus.get("traductionFichiers", [])
        if trad_fichiers and len(trad_fichiers) > 0:
            return trad_fichiers[0].get("url", "")
            
        # Sécurités de secours
        if "url" in first_illus:
            return first_illus.get("url", "")
        traduc = first_illus.get("traductionMetadonnees", {})
        if isinstance(traduc, dict):
            return traduc.get("url", "")
    return ""

def interroger_apidae(id_selection):
    query_params = {
        "apiKey": API_KEY,
        "projetId": int(PROJECT_ID),
        "selectionIds": [int(id_selection)],
        "count": 1000
    }
    payload = {"query": json.dumps(query_params)}
    try:
        response = requests.post(API_URL, data=payload)
        if response.status_code == 200:
            return response.json().get("objetsTouristiques", [])
        return []
    except Exception as e:
        print(f"Erreur de connexion : {e}")
        return []

def main():
    if not API_KEY or not PROJECT_ID:
        print("Erreur : Clés manquantes.")
        return

    for name_key, info in CATEGORIES.items():
        print(f"Extraction Apidae V002 -> {name_key}...")
        objets = interroger_apidae(info["id_selection"])
        
        for obj in objets:
            geoloc = obj.get("localisation", {}).get("geolocalisation", {})
            geo_json_data = geoloc.get("geoJson", {})
            points = geo_json_data.get("coordinates", [])
            
            if not points or len(points) < 2: 
                continue
                
            nom = obj.get("nom", {}).get("libelleFr", "")
            desc = obj.get("presentation", {}).get("descriptifCourt", {}).get("libelleFr", "")
            adresse = get_adresse(obj)
            tel, email, web = extract_contacts(obj)
            photo = extract_photo(obj)
            
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": points
                },
                "properties": {
                    "nom": nom,
                    "description": clean_html(desc),
                    "adresse": adresse,
                    "telephone": tel,
                    "email": email,
                    "site_web": web,
                    "photo": photo
                }
            }
            info["features"].append(feature)
            
        filename = f"{name_key}.geojson"
        geojson_output = {"type": "FeatureCollection", "features": info["features"]}
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(geojson_output, f, ensure_ascii=False, indent=4)
        print(f"Fichier créé : {filename} ({len(info['features'])} objets).")

if __name__ == "__main__":
    main()
