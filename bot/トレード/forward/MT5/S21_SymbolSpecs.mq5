//+------------------------------------------------------------------+
//| S21_SymbolSpecs.mq5  (2026-10-27)                                 |
//| 全銘柄の仕様（スワップ・契約サイズ・桁・スプレッドなど）を CSV に書き出す。 |
//| bot（S21・S23・S17b）のスワップ換算・ロット計算・銘柄名の対応づけに使う。   |
//| 置き場所: MT5「ファイル」→「データフォルダを開く」→ MQL5/Scripts         |
//| 出力:     MQL5/Files/symbol_specs_YYYYMMDD_HHMM.csv                  |
//| 売買はしない（読むだけ）。                                          |
//+------------------------------------------------------------------+
#property copyright "taichi"
#property version   "1.00"
#property script_show_inputs

input bool AllSymbols = true;   // true = サーバーの全銘柄 / false = 気配値表示の銘柄だけ

string SwapModeName(const long m)
  {
   if(m == 0) return "DISABLED";
   if(m == 1) return "POINTS";
   if(m == 2) return "CURRENCY_SYMBOL";
   if(m == 3) return "CURRENCY_MARGIN";
   if(m == 4) return "CURRENCY_DEPOSIT";
   if(m == 5) return "INTEREST_CURRENT";
   if(m == 6) return "INTEREST_OPEN";
   if(m == 7) return "REOPEN_CURRENT";
   if(m == 8) return "REOPEN_BID";
   if(m == 9) return "CURRENCY_PROFIT";
   return "UNKNOWN_" + IntegerToString(m);
  }

string Clean(string s)
  {
   StringReplace(s, ",", " ");
   StringReplace(s, "\r", " ");
   StringReplace(s, "\n", " ");
   return s;
  }

string Num(const double v) { return DoubleToString(v, 8); }

void OnStart()
  {
   MqlDateTime t;
   TimeToStruct(TimeLocal(), t);
   string fn = StringFormat("symbol_specs_%04d%02d%02d_%02d%02d.csv", t.year, t.mon, t.day, t.hour, t.min);
   int h = FileOpen(fn, FILE_WRITE | FILE_TXT | FILE_ANSI);
   if(h == INVALID_HANDLE)
     {
      Print("ファイルを開けない: ", GetLastError());
      return;
     }
   FileWriteString(h, "name,description,path,digits,point,contract_size,currency_base,currency_profit,currency_margin,"
                      "swap_mode,swap_mode_name,swap_long,swap_short,swap_3days,spread_points,spread_float,bid,ask,"
                      "tick_value,tick_size,volume_min,volume_step,volume_max,trade_mode,"
                      "account_currency,account_leverage,server,company\r\n");
   string acc_ccy = AccountInfoString(ACCOUNT_CURRENCY);
   long   acc_lev = AccountInfoInteger(ACCOUNT_LEVERAGE);
   string server  = Clean(AccountInfoString(ACCOUNT_SERVER));
   string company = Clean(AccountInfoString(ACCOUNT_COMPANY));
   bool selected_only = !AllSymbols;
   int n = SymbolsTotal(selected_only);
   int written = 0;
   for(int i = 0; i < n; i++)
     {
      string s = SymbolName(i, selected_only);
      if(s == "") continue;
      long   mode = SymbolInfoInteger(s, SYMBOL_SWAP_MODE);
      string row =
         s + "," +
         Clean(SymbolInfoString(s, SYMBOL_DESCRIPTION)) + "," +
         Clean(SymbolInfoString(s, SYMBOL_PATH)) + "," +
         IntegerToString(SymbolInfoInteger(s, SYMBOL_DIGITS)) + "," +
         Num(SymbolInfoDouble(s, SYMBOL_POINT)) + "," +
         Num(SymbolInfoDouble(s, SYMBOL_TRADE_CONTRACT_SIZE)) + "," +
         SymbolInfoString(s, SYMBOL_CURRENCY_BASE) + "," +
         SymbolInfoString(s, SYMBOL_CURRENCY_PROFIT) + "," +
         SymbolInfoString(s, SYMBOL_CURRENCY_MARGIN) + "," +
         IntegerToString(mode) + "," +
         SwapModeName(mode) + "," +
         Num(SymbolInfoDouble(s, SYMBOL_SWAP_LONG)) + "," +
         Num(SymbolInfoDouble(s, SYMBOL_SWAP_SHORT)) + "," +
         IntegerToString(SymbolInfoInteger(s, SYMBOL_SWAP_ROLLOVER3DAYS)) + "," +
         IntegerToString(SymbolInfoInteger(s, SYMBOL_SPREAD)) + "," +
         IntegerToString(SymbolInfoInteger(s, SYMBOL_SPREAD_FLOAT)) + "," +
         Num(SymbolInfoDouble(s, SYMBOL_BID)) + "," +
         Num(SymbolInfoDouble(s, SYMBOL_ASK)) + "," +
         Num(SymbolInfoDouble(s, SYMBOL_TRADE_TICK_VALUE)) + "," +
         Num(SymbolInfoDouble(s, SYMBOL_TRADE_TICK_SIZE)) + "," +
         Num(SymbolInfoDouble(s, SYMBOL_VOLUME_MIN)) + "," +
         Num(SymbolInfoDouble(s, SYMBOL_VOLUME_STEP)) + "," +
         Num(SymbolInfoDouble(s, SYMBOL_VOLUME_MAX)) + "," +
         IntegerToString(SymbolInfoInteger(s, SYMBOL_TRADE_MODE)) + "," +
         acc_ccy + "," + IntegerToString(acc_lev) + "," + server + "," + company + "\r\n";
      FileWriteString(h, row);
      written++;
     }
   FileClose(h);
   string path = TerminalInfoString(TERMINAL_DATA_PATH) + "\\MQL5\\Files\\" + fn;
   Print("書き出した: ", written, " 銘柄 → ", path);
   Alert("S21_SymbolSpecs: ", written, " 銘柄を書き出した → ", fn);
  }
//+------------------------------------------------------------------+
