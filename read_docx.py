import pandas as pd

CSV_PATH = 'masterfile_claims.csv'
UPDATED_CSV_PATH = 'masterfile_claims_UPDATED.csv'

def update_camu_camu_vitc_dosage():
    df = pd.read_csv(CSV_PATH)
    mask = df['Ingredient'].str.contains('camu camu', case=False, na=False) & df['Claim'].str.contains('vitamin c', case=False, na=False)
    df.loc[mask, 'Dosage'] = '≥ 12 mg vitamin C per serving'
    df.to_csv(UPDATED_CSV_PATH, index=False)
    print(f"Updated {mask.sum()} rows. Saved to {UPDATED_CSV_PATH}")

if __name__ == '__main__':
    update_camu_camu_vitc_dosage()
