//+------------------------------------------------------------------+
//| S21_SpreadLogger.mq5  (2026-10-27)  — サービス（チャート不要）        |
//| bot の銘柄のスプレッドを数秒おきに測り、1 時間ごとにまとめて CSV に足す。  |
//| 目的: 運用規程 §4 の実弾条件③「実測コストが 1R の 3% 以内」と、           |
//|       Q539（S21 は損益分岐がスプレッド約 2.16 倍）を実際の口座で確かめる。 |
//| 置き場所: MQL5/Services → ナビゲーターの「サービス」で右クリック→追加→開始 |
//| 出力:     MQL5/Files/spreads_YYYYMM.csv（月ごと・追記）              |
//| 売買はしない（読むだけ）。MT5 を開いている間だけ測る。                 |
//+------------------------------------------------------------------+
#property service
#property copyright "taichi"
#property version   "1.00"

input string Symbols   = "EURUSD,GBPUSD,AUDUSD,NZDUSD,USDJPY,USDCHF,USDCAD,EURJPY,GBPJPY,EURGBP,XAUUSD,US500,USTECH,GER40,JPN225,AUDJPY,CADJPY,CHFJPY,NZDJPY,BTCUSD,ETHUSD";
input int    SampleSec = 5;    // 何秒おきに測るか
input int    FreshSec  = 60;   // これより古い気配は数えない（休場中の止まった値を除く）

string want[];
string sym[];
int    ns = 0;
long   cnt[];
double sum[], mn[], mx[], firstPts[], firstMid[], sumPx[];

//--- 銘柄名の言い換え（業者ごとに名前が違う指数・金）
string Aliases(const string w)
  {
   if(w == "US500")  return "US500|SPX500|SP500|US500.cash|US500Cash";
   if(w == "USTECH") return "USTECH|US100|NAS100|USTEC|NDX100|US100.cash";
   if(w == "GER40")  return "GER40|DE40|DAX40|GER30|DE30|GER40.cash";
   if(w == "JPN225") return "JPN225|JP225|NIKKEI225|JPN225.cash|JP225Cash";
   if(w == "XAUUSD") return "XAUUSD|GOLD";
   return w;
  }

string Resolve(const string w)
  {
   string c[];
   int k = StringSplit(Aliases(w), '|', c);
   for(int j = 0; j < k; j++)               // 1) 名前がそのまま一致
      if(SymbolSelect(c[j], true)) return c[j];
   int n = SymbolsTotal(false);
   for(int j = 0; j < k; j++)               // 2) 先頭が一致（EURUSD.f・EURUSDm など）
      for(int i = 0; i < n; i++)
        {
         string s = SymbolName(i, false);
         if(StringFind(s, c[j]) == 0 && StringLen(s) <= StringLen(c[j]) + 6)
            if(SymbolSelect(s, true)) return s;
        }
   return "";
  }

void ResetStats()
  {
   for(int i = 0; i < ns; i++)
     {
      cnt[i] = 0; sum[i] = 0; sumPx[i] = 0; mn[i] = DBL_MAX; mx[i] = 0; firstPts[i] = -1; firstMid[i] = 0;
     }
  }

void Flush(const long hourKey)
  {
   datetime hu = (datetime)(hourKey * 3600);
   MqlDateTime t;
   TimeToStruct(hu, t);
   string fn = StringFormat("spreads_%04d%02d.csv", t.year, t.mon);
   int h = FileOpen(fn, FILE_READ | FILE_WRITE | FILE_TXT | FILE_ANSI);
   if(h == INVALID_HANDLE) { Print("spreads: ファイルを開けない ", GetLastError()); return; }
   if(FileSize(h) == 0)
      FileWriteString(h, "hour_utc,server_offset_sec,want,symbol,n,mean_pts,min_pts,max_pts,open_pts,mean_spread_price,mid_open,point\r\n");
   FileSeek(h, 0, SEEK_END);
   long off = (long)(TimeTradeServer() - TimeGMT());
   for(int i = 0; i < ns; i++)
     {
      if(cnt[i] == 0) continue;            // 休場の時間は書かない
      double pt = SymbolInfoDouble(sym[i], SYMBOL_POINT);
      string row = TimeToString(hu, TIME_DATE | TIME_MINUTES) + "," + IntegerToString(off) + "," + want[i] + "," + sym[i] + "," +
                   IntegerToString(cnt[i]) + "," + DoubleToString(sum[i] / cnt[i], 2) + "," + DoubleToString(mn[i], 1) + "," +
                   DoubleToString(mx[i], 1) + "," + DoubleToString(firstPts[i], 1) + "," + DoubleToString(sumPx[i] / cnt[i], 8) + "," +
                   DoubleToString(firstMid[i], 8) + "," + DoubleToString(pt, 8) + "\r\n";
      FileWriteString(h, row);
     }
   FileClose(h);
  }

void OnStart()
  {
   string w[];
   int k = StringSplit(Symbols, ',', w);
   for(int i = 0; i < k; i++)
     {
      string x = w[i];
      StringTrimLeft(x); StringTrimRight(x);
      if(x == "") continue;
      string s = Resolve(x);
      if(s == "") { Print("spreads: 見つからない銘柄 ", x); continue; }
      ArrayResize(want, ns + 1); ArrayResize(sym, ns + 1);
      want[ns] = x; sym[ns] = s; ns++;
      Print("spreads: ", x, " → ", s);
     }
   ArrayResize(cnt, ns); ArrayResize(sum, ns); ArrayResize(sumPx, ns); ArrayResize(mn, ns); ArrayResize(mx, ns);
   ArrayResize(firstPts, ns); ArrayResize(firstMid, ns);
   ResetStats();
   long cur = (long)TimeGMT() / 3600;
   Print("spreads: 開始 ", ns, " 銘柄・", SampleSec, " 秒おき");
   while(!IsStopped())
     {
      long hk = (long)TimeGMT() / 3600;
      if(hk != cur) { Flush(cur); ResetStats(); cur = hk; }
      datetime now = TimeTradeServer();
      for(int i = 0; i < ns; i++)
        {
         MqlTick tk;
         if(!SymbolInfoTick(sym[i], tk)) continue;
         if(tk.bid <= 0 || tk.ask <= 0 || now - tk.time > FreshSec) continue;
         double pt = SymbolInfoDouble(sym[i], SYMBOL_POINT);
         if(pt <= 0) continue;
         double px = tk.ask - tk.bid, pts = px / pt;
         cnt[i]++; sum[i] += pts; sumPx[i] += px;
         if(pts < mn[i]) mn[i] = pts;
         if(pts > mx[i]) mx[i] = pts;
         if(firstPts[i] < 0) { firstPts[i] = pts; firstMid[i] = (tk.ask + tk.bid) / 2.0; }
        }
      Sleep(SampleSec * 1000);
     }
   Flush(cur);
   Print("spreads: 停止");
  }
//+------------------------------------------------------------------+
