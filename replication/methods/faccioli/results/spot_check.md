# Faccioli spot check: filtered glucose, dG and Res around each detection

Main rule refractory, Route B, our matching rule. One participant-day per group: the first day with at least one TP and one FP. Each block shows samples -15 to +15 min around a kept detection (5-min samples). g = QC'd glucose, cgm = causal 3-point median, dG = Kalman derivative (mg/dL/min), Res = observer residual (mg/dL). flag = Res > Th_Res and dG > Th_Der. Thresholds and L are the held-out fold's locked set.

## healthy: CGMacros-001_2020-05-07, fold_0: Th_Res 1 mg/dL, Th_Der 0.5 mg/dL/min, L 0.0325 mg/dL/min^2

Detection 00:24, status not_scored

```
 min      g    cgm     dG     Res  Res>Th dG>Th  flag
 -15   97.0    nan    nan     nan       0     0     0
 -10   99.0   99.0    nan    0.00       0     0     0
  -5  104.0   99.0    nan    0.00       0     0     0
  +0  106.0  104.0   0.83    2.13       1     1     1
  +5  107.0  106.0   0.82    1.00       0     1     0
 +10  109.0  107.0   0.46    0.00       0     0     0
 +15  111.0  109.0   0.35    0.00       0     0     0
```

Detection 10:44, status TP, delay 37 min

```
 min      g    cgm     dG     Res  Res>Th dG>Th  flag
 -15  109.0  110.0  -0.03    0.00       0     0     0
 -10  114.0  111.0  -0.02    0.33       0     0     0
  -5  127.0  114.0   0.11    1.11       1     0     0
  +0  140.0  127.0   0.71    8.49       1     1     1
  +5  138.0  138.0   1.41   12.20       1     1     1
 +10  134.0  138.0   1.61    5.54       1     1     1
 +15  133.0  134.0   1.31   -0.30       0     1     0
```

Detection 13:14, status FP

```
 min      g    cgm     dG     Res  Res>Th dG>Th  flag
 -15  103.0  103.0  -0.08    0.00       0     0     0
 -10  108.0  103.0  -0.07    0.07       0     0     0
  -5  115.0  108.0   0.16    2.48       1     0     0
  +0  115.0  115.0   0.57    5.08       1     1     1
  +5  110.0  115.0   0.73    1.30       1     1     1
 +10  108.0  110.0   0.52   -2.79       0     1     0
 +15  105.0  108.0   0.23   -2.93       0     0     0
```

Detection 18:49, status not_scored

```
 min      g    cgm     dG     Res  Res>Th dG>Th  flag
 -15   98.0   89.0  -0.61    4.02       1     0     0
 -10   96.0   96.0  -0.01    8.83       1     0     0
  -5   98.0   98.0   0.46    7.96       1     0     0
  +0   97.0   97.0   0.66    4.22       1     1     1
  +5   93.0   97.0   0.71    1.64       1     1     1
 +10   96.0   96.0   0.60    0.00       0     1     0
 +15   96.0   96.0   0.46    0.00       0     0     0
```

Detection 21:19, status not_scored

```
 min      g    cgm     dG     Res  Res>Th dG>Th  flag
 -15   96.0   96.0  -0.15   -0.36       0     0     0
 -10  103.0   96.0  -0.10    0.02       0     0     0
  -5  107.0  103.0   0.25    4.00       1     0     0
  +0  112.0  107.0   0.60    4.06       1     1     1
  +5  120.0  112.0   0.94    4.19       1     1     1
 +10  128.0  120.0   1.35    5.90       1     1     1
 +15  136.0  128.0   1.72    6.55       1     1     1
```

## prediabetes: CGMacros-008_2023-02-01, fold_1: Th_Res 1 mg/dL, Th_Der 0.5 mg/dL/min, L 0.0325 mg/dL/min^2

Detection 08:13, status TP, delay 21 min

```
 min      g    cgm     dG     Res  Res>Th dG>Th  flag
 -15  123.0  123.0   0.05    0.00       0     0     0
 -10  128.0  123.0   0.09    0.03       0     0     0
  -5  150.0  128.0   0.34    2.32       1     0     0
  +0  165.0  150.0   1.36   17.18       1     1     1
  +5  172.0  165.0   2.40   23.23       1     1     1
 +10  173.0  172.0   2.94   20.74       1     1     1
 +15  176.0  173.0   2.86   12.70       1     1     1
```

Detection 11:08, status FP

```
 min      g    cgm     dG     Res  Res>Th dG>Th  flag
 -15   96.0   96.0  -0.82    3.03       1     0     0
 -10  100.0   96.0  -0.38    3.44       1     0     0
  -5  108.0  100.0   0.17    6.13       1     0     0
  +0  109.0  108.0   0.86   10.82       1     1     1
  +5  109.0  109.0   1.24    8.20       1     1     1
 +10  108.0  109.0   1.32    4.64       1     1     1
 +15  106.0  108.0   1.16    0.85       0     1     0
```

Detection 13:38, status TP, delay 76 min

```
 min      g    cgm     dG     Res  Res>Th dG>Th  flag
 -15  101.0   93.0  -0.14    2.04       1     0     0
 -10  103.0  101.0   0.23    6.64       1     0     0
  -5  104.0  103.0   0.49    4.84       1     0     0
  +0  105.0  104.0   0.62    2.15       1     1     1
  +5  104.0  104.0   0.59    0.00       0     1     0
 +10  103.0  104.0   0.48   -0.40       0     0     0
 +15  107.0  104.0   0.33   -0.18       0     0     0
```

Detection 19:48, status not_scored

```
 min      g    cgm     dG     Res  Res>Th dG>Th  flag
 -15  105.0  103.0  -0.17    0.00       0     0     0
 -10  106.0  105.0   0.01    0.31       0     0     0
  -5  115.0  106.0   0.18    0.00       0     0     0
  +0  133.0  115.0   0.63    4.07       1     1     1
  +5  146.0  133.0   1.56   13.92       1     1     1
 +10  154.0  146.0   2.42   17.31       1     1     1
 +15  160.0  154.0   2.90   15.15       1     1     1
```

## T2D: CGMacros-003_2020-03-13, fold_2: Th_Res 1 mg/dL, Th_Der 0.5 mg/dL/min, L 0.0325 mg/dL/min^2

Detection 08:49, status TP, delay 22 min

```
 min      g    cgm     dG     Res  Res>Th dG>Th  flag
 -15  121.0  118.0   0.06    0.86       0     0     0
 -10  123.0  121.0   0.24    0.83       0     0     0
  -5  133.0  123.0   0.39    0.01       0     0     0
  +0  148.0  133.0   0.84    3.80       1     1     1
  +5  154.0  148.0   1.60   10.05       1     1     1
 +10  159.0  154.0   2.05    7.08       1     1     1
 +15  176.8  159.0   2.20    3.35       1     1     1
```

Detection 10:54, status FP

```
 min      g    cgm     dG     Res  Res>Th dG>Th  flag
 -15  110.0  114.0   1.00   -1.67       0     1     0
 -10  107.0  110.0   1.08    0.00       0     1     0
  -5  104.0  107.0   0.92    0.67       0     1     0
  +0  108.0  107.0   0.75    2.44       1     1     1
  +5  110.0  108.0   0.62    3.79       1     1     1
 +10  111.0  110.0   0.56    4.89       1     1     1
 +15  111.0  111.0   0.49    4.29       1     0     0
```

Detection 16:39, status not_scored

```
 min      g    cgm     dG     Res  Res>Th dG>Th  flag
 -15  109.0  107.0  -0.64    0.16       0     0     0
 -10  116.0  109.0  -0.37    0.77       0     0     0
  -5  125.0  116.0   0.15    3.98       1     0     0
  +0  131.0  125.0   0.83    7.34       1     1     1
  +5  133.0  131.0   1.37    6.91       1     1     1
 +10  131.0  131.0   1.50    1.49       1     1     1
 +15  128.0  131.0   1.36   -0.47       0     1     0
```

Detection 21:09, status not_scored

```
 min      g    cgm     dG     Res  Res>Th dG>Th  flag
 -15   91.0   90.0   0.13    0.00       0     0     0
 -10   93.0   91.0   0.15    0.00       0     0     0
  -5  100.0   93.0   0.22    0.01       0     0     0
  +0  111.0  100.0   0.51    2.21       1     1     1
  +5  125.0  111.0   1.06    6.17       1     1     1
 +10  136.0  125.0   1.80   11.09       1     1     1
 +15  148.0  136.0   2.41   11.95       1     1     1
```

