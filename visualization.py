import os
from pathlib import Path
import dtale
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
# ---------------------------- settings ---------------------------------
BASE_DIR = Path(__file__).parent
FIG_DIR = Path("~/Documents/gitprojects/auerbenji/assets/images").expanduser()
MIN_LTR = 80
MAX_LTR = 1000
SAVE_CSV = True
SHOW_PLT = True
SAVE_SVG = True
CSV_FILENAME = "results.csv"

# exact identifiers present in the 'Visual' sheet (row 0)
ID_ABO = "abo subject to optimization"
ID_ABO="abo subject to optimization"
ID_CTS="cost to serve"
ID_CG="cost of good"
ID_CW="cost of warehouse"
ID_CC="cost of carrier incl penalty"
ID_CP="cost of penalty"
ID_PROP_CG="CG of CTS"
ID_PROP_CW="CW of CTS"
ID_PROP_CC="CC of CTS"
ID_GEN="model gen time"
ID_OPT="model opt time"
ID_TOT="total parcels shipped"
ID_LPV="levelized parcel value"
# created by script
ID_RWS = "rel warehouse savings vs 80 [%]"
ID_RCS = "rel carrier savings vs 80 [%]"
# -----------------------------------------------------------------------

# use
# dtale.show(df).open_browser()
# to view large pandas files

def get_path(s: int) -> str:
    pwdpath = os.getcwd()
    path2data = pwdpath + '/results-' + str(s) + '-ltr-det.xlsx' # output document
    return path2data

def series_cutter(s: int) -> pd.Series:
    path = get_path(s)
    df = pd.read_excel(path, sheet_name="Visual", header=1, nrows=1)
    df = df.drop(df.columns[0], axis=1)   # drop left-most column
    row = df.iloc[0]  # convert dataFrame to series
    return row

def contact_fast(MIN_LTR: int, MAX_LTR: int) -> pd.DataFrame:
    rows = [series_cutter(s) for s in range(MIN_LTR, MAX_LTR+1, 20)]
    df = pd.DataFrame(rows).reset_index(drop=True)
    return df

def cal_savings(df: pd.DataFrame) -> pd.DataFrame:
    df.loc[:,ID_RWS] = (1 - df.loc[:,ID_CW]/df.loc[0,ID_CW])*100
    df.loc[:,ID_RCS] = (1 - df.loc[:,ID_CC]/df.loc[0,ID_CC])*100
    # Adjust into percentage
    df.loc[:,ID_PROP_CG] = df.loc[:,ID_PROP_CG]*100
    df.loc[:,ID_PROP_CW] = df.loc[:,ID_PROP_CW]*100
    df.loc[:,ID_PROP_CC] = df.loc[:,ID_PROP_CC]*100
    return df

def visualize(df: pd.DataFrame, outdir: Path):
    x = df[ID_ABO].values
    colors = ["tab:blue", "tab:orange", "tab:green"]

    # figure 1: cost curves and cost proportions
    fig1, ax11 = plt.subplots()

    # left axis (solid lines)
    ax11.plot(x, df[ID_CTS], label="$CTS$", color=colors[0], linestyle="-")
    ax11.plot(x, df[ID_CW],  label="$CW$",  color=colors[1], linestyle="-")
    ax11.plot(x, df[ID_CC],  label="$CC$",  color=colors[2], linestyle="-")

    ax11.set_xlabel("Subscription size (ltr)")
    ax11.set_ylabel("Cost (EUR)")
    ax11.set_ylim(0, 1)
    ax11.grid(True, linestyle=":")

    # right axis (dashed lines, same colors)
    ax12 = ax11.twinx()
    ax12.plot(x, df[ID_PROP_CG], label="$\dfrac{CG}{CTS}$", color=colors[0], linestyle="--")
    ax12.plot(x, df[ID_PROP_CW], label="$\dfrac{CW}{CTS}$", color=colors[1], linestyle="--")
    ax12.plot(x, df[ID_PROP_CC], label="$\dfrac{CC}{CTS}$", color=colors[2], linestyle="--")
    ax12.set_ylabel("Proportion (%)")
    ax12.set_ylim(0, 100)

    # merge legends from both axes
    lines1, labels1 = ax11.get_legend_handles_labels()
    lines2, labels2 = ax12.get_legend_handles_labels()
    ax11.legend(lines1 + lines2, labels1 + labels2, loc="best")


    # figure 2: relative warehouse savings
    fig2, ax2 = plt.subplots()

    # explicit colors to avoid duplicates
    colors = ["tab:blue", "tab:orange", "tab:green"]

    # left axis (solid lines)
    ax2.plot(x, df[ID_RWS], label="$\eta_W$", color=colors[1], linestyle="--")
    ax2.plot(x, df[ID_RCS],  label="$\eta_C$",  color=colors[2], linestyle="--")
    ax2.axhline(y=df[ID_RCS].max(), color="red", linestyle="--", linewidth=1.5, label=f"$\max(\eta_C)$ = {df[ID_RCS].max():.2f}")

    ax2.set_xlabel("Subscription size (ltr)")
    ax2.set_ylabel("Relative savings (compared to 80 ltr subscription) (%)")
    ax2.set_ylim(0, 100)
    ax2.grid(True, linestyle=":")
    ax2.legend(loc="best")


    # figure 3: levelized CTS per parcel
    fig3, ax31 = plt.subplots()

    ax31.plot(x, df[ID_LPV], label="$LPV$", color=colors[0], linestyle="-")
    # vertical line at subscription size = 110
    ax31.axhline(y=df[ID_LPV].max(), color="red", linestyle="--", linewidth=1.5, label=f"$\max(LPV)$ = {df[ID_LPV].max():.0f}")

    ax31.set_xlabel("Subscription size (ltr)")
    ax31.set_ylabel("Parcel value (EUR/parcel)")
    ax31.set_ylim(50, 150)
    ax31.grid(True, linestyle=":")

    ax32 = ax31.twinx()
    width = (np.min(np.diff(np.unique(x))) * 0.6) if len(x) > 1 else 0.6
    ax32.bar(x, df[ID_TOT], width=width, alpha=0.5, label="Parcels shipped",color=colors[0])

    ax32.set_ylabel("Parcels (-)")
    ax32.set_ylim(0, 10)
    ax32.set_yticks(range(0, 11, 1))

    # merge legends from both axes
    lines1, labels1 = ax31.get_legend_handles_labels()
    lines2, labels2 = ax32.get_legend_handles_labels()
    ax31.legend(lines1 + lines2, labels1 + labels2, loc="upper left")


    #figure 4: carrier cost
    cost = np.array([3.62, 4.17, 4.83, 6.3, 6.85, 7.02, 7.29])
    weight = np.array([1.5, 3.5, 8.5, 13.5, 18.5, 23.5, 30])
    cost_per_weight = cost/weight

    fig4, ax41 = plt.subplots()

    ax41.plot(weight, cost, label="$SC$", color=colors[0], linestyle="-")

    ax41.set_xlabel("Parcel weight (kg)")
    ax41.set_ylabel("Parcel cost (EUR)")
    ax41.set_ylim(0, 10)
    ax41.grid(True, linestyle=":")

    ax42 = ax41.twinx()
    ax42.plot(weight, cost_per_weight, label="$\dfrac{SC}{SW}$",color=colors[1])

    ax42.set_ylabel("Cost per weight (EUR/kg)")
    ax42.set_ylim(0, 3)

    # merge legends from both axes
    lines1, labels1 = ax41.get_legend_handles_labels()
    lines2, labels2 = ax42.get_legend_handles_labels()
    ax42.legend(lines1 + lines2, labels1 + labels2, loc="upper center")



    if SHOW_PLT:
        plt.show()

    if SAVE_SVG:
        fig1.savefig(outdir / "cost-of-species.svg", format="svg", bbox_inches="tight")
        fig2.savefig(outdir / "relative-savings.svg", format="svg", bbox_inches="tight")
        fig3.savefig(outdir / "parcel-value.svg", format="svg", bbox_inches="tight")
        fig4.savefig(outdir / "V-vector.svg", format="svg", bbox_inches="tight")

def main():
    df = contact_fast(MIN_LTR,MAX_LTR)
    df = cal_savings(df)
    if SAVE_CSV:
        df.to_csv(BASE_DIR / CSV_FILENAME, index=False)
    visualize(df, FIG_DIR)

if __name__ == "__main__":
    main()
