import matplotlib.pyplot as plt
import pandas as pd

df = pd.read_csv("results.csv")
df.plot(x="epoch", y="loss")
plt.savefig("loss.png")
