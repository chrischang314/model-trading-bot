/ Minimal q schema for the toy trading system.

.bot.dbdir:getenv `KDB_DATA_DIR;
if[0=count .bot.dbdir;.bot.dbdir:"/data/kdb"];
system "mkdir -p ",.bot.dbdir;

.bot.path:{[name] `$":",.bot.dbdir,"/",string name};
.bot.exists:{[name] name in key `$":",.bot.dbdir};

.bot.emptyBars:{
  ([] date:`date$();
      sym:`symbol$();
      open:`float$();
      high:`float$();
      low:`float$();
      close:`float$();
      adj_close:`float$();
      volume:`long$();
      source:`symbol$())
  };

.bot.emptySignals:{
  ([] date:`date$();
      sym:`symbol$();
      close:`float$();
      sma_20:`float$();
      sma_50:`float$();
      rsi_14:`float$();
      macd:`float$();
      macd_signal:`float$();
      macd_hist:`float$();
      trade_signal:`symbol$();
      position:`int$())
  };

bars:$[.bot.exists `bars;get .bot.path[`bars];.bot.emptyBars[]];
signals:$[.bot.exists `signals;get .bot.path[`signals];.bot.emptySignals[]];

.bot.save:{
  (.bot.path[`bars]) set bars;
  (.bot.path[`signals]) set signals;
  ::;
  };

.bot.normBars:{[t]
  update date:`date$date,
         sym:`$sym,
         open:`float$open,
         high:`float$high,
         low:`float$low,
         close:`float$close,
         adj_close:`float$adj_close,
         volume:`long$volume,
         source:`$source
    from t
  };

.bot.normSignals:{[t]
  update date:`date$date,
         sym:`$sym,
         close:`float$close,
         sma_20:`float$sma_20,
         sma_50:`float$sma_50,
         rsi_14:`float$rsi_14,
         macd:`float$macd,
         macd_signal:`float$macd_signal,
         macd_hist:`float$macd_hist,
         trade_signal:`$trade_signal,
         position:`int$position
    from t
  };

.bot.upsertBars:{[t]
  t:.bot.normBars t;
  bars,:t;
  bars::`date`sym xasc 0!select open:last open,
                              high:last high,
                              low:last low,
                              close:last close,
                              adj_close:last adj_close,
                              volume:last volume,
                              source:last source
                            by date,sym from bars;
  .bot.save[];
  count bars
  };

.bot.upsertSignals:{[t]
  t:.bot.normSignals t;
  signals,:t;
  signals::`date`sym xasc 0!select close:last close,
                                  sma_20:last sma_20,
                                  sma_50:last sma_50,
                                  rsi_14:last rsi_14,
                                  macd:last macd,
                                  macd_signal:last macd_signal,
                                  macd_hist:last macd_hist,
                                  trade_signal:last trade_signal,
                                  position:last position
                                by date,sym from signals;
  .bot.save[];
  count signals
  };
