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
      ema_12:`float$();
      ema_26:`float$();
      sma_20:`float$();
      sma_50:`float$();
      rsi_14:`float$();
      macd:`float$();
      macd_signal:`float$();
      macd_hist:`float$();
      bb_mid:`float$();
      bb_upper:`float$();
      bb_lower:`float$();
      bb_width:`float$();
      atr_14:`float$();
      atr_pct:`float$();
      stoch_k:`float$();
      stoch_d:`float$();
      obv:`float$();
      volume_z:`float$();
      momentum_20d:`float$();
      distance_52w_high:`float$();
      trend_score:`float$();
      momentum_score:`float$();
      volatility_score:`float$();
      volume_score:`float$();
      signal_score:`float$();
      signal_reason:();
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
         ema_12:`float$ema_12,
         ema_26:`float$ema_26,
         sma_20:`float$sma_20,
         sma_50:`float$sma_50,
         rsi_14:`float$rsi_14,
         macd:`float$macd,
         macd_signal:`float$macd_signal,
         macd_hist:`float$macd_hist,
         bb_mid:`float$bb_mid,
         bb_upper:`float$bb_upper,
         bb_lower:`float$bb_lower,
         bb_width:`float$bb_width,
         atr_14:`float$atr_14,
         atr_pct:`float$atr_pct,
         stoch_k:`float$stoch_k,
         stoch_d:`float$stoch_d,
         obv:`float$obv,
         volume_z:`float$volume_z,
         momentum_20d:`float$momentum_20d,
         distance_52w_high:`float$distance_52w_high,
         trend_score:`float$trend_score,
         momentum_score:`float$momentum_score,
         volatility_score:`float$volatility_score,
         volume_score:`float$volume_score,
         signal_score:`float$signal_score,
         signal_reason:signal_reason,
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
                                  ema_12:last ema_12,
                                  ema_26:last ema_26,
                                  sma_20:last sma_20,
                                  sma_50:last sma_50,
                                  rsi_14:last rsi_14,
                                  macd:last macd,
                                  macd_signal:last macd_signal,
                                  macd_hist:last macd_hist,
                                  bb_mid:last bb_mid,
                                  bb_upper:last bb_upper,
                                  bb_lower:last bb_lower,
                                  bb_width:last bb_width,
                                  atr_14:last atr_14,
                                  atr_pct:last atr_pct,
                                  stoch_k:last stoch_k,
                                  stoch_d:last stoch_d,
                                  obv:last obv,
                                  volume_z:last volume_z,
                                  momentum_20d:last momentum_20d,
                                  distance_52w_high:last distance_52w_high,
                                  trend_score:last trend_score,
                                  momentum_score:last momentum_score,
                                  volatility_score:last volatility_score,
                                  volume_score:last volume_score,
                                  signal_score:last signal_score,
                                  signal_reason:last signal_reason,
                                  trade_signal:last trade_signal,
                                  position:last position
                                by date,sym from signals;
  .bot.save[];
  count signals
  };
