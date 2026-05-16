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
      return_1d:`float$();
      return_5d:`float$();
      return_21d:`float$();
      return_63d:`float$();
      ema_12:`float$();
      ema_26:`float$();
      ema_50:`float$();
      sma_20:`float$();
      sma_50:`float$();
      sma_200:`float$();
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
      realized_vol_20:`float$();
      realized_vol_63:`float$();
      stoch_k:`float$();
      stoch_d:`float$();
      williams_r_14:`float$();
      cci_20:`float$();
      adx_14:`float$();
      plus_di_14:`float$();
      minus_di_14:`float$();
      obv:`float$();
      volume_z:`float$();
      rolling_vwap_20:`float$();
      momentum_20d:`float$();
      momentum_252_skip_21:`float$();
      zscore_20:`float$();
      donchian_high_20:`float$();
      donchian_low_20:`float$();
      donchian_breakout:`float$();
      keltner_mid:`float$();
      keltner_upper:`float$();
      keltner_lower:`float$();
      gap_return:`float$();
      intraday_return:`float$();
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
         return_1d:`float$return_1d,
         return_5d:`float$return_5d,
         return_21d:`float$return_21d,
         return_63d:`float$return_63d,
         ema_12:`float$ema_12,
         ema_26:`float$ema_26,
         ema_50:`float$ema_50,
         sma_20:`float$sma_20,
         sma_50:`float$sma_50,
         sma_200:`float$sma_200,
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
         realized_vol_20:`float$realized_vol_20,
         realized_vol_63:`float$realized_vol_63,
         stoch_k:`float$stoch_k,
         stoch_d:`float$stoch_d,
         williams_r_14:`float$williams_r_14,
         cci_20:`float$cci_20,
         adx_14:`float$adx_14,
         plus_di_14:`float$plus_di_14,
         minus_di_14:`float$minus_di_14,
         obv:`float$obv,
         volume_z:`float$volume_z,
         rolling_vwap_20:`float$rolling_vwap_20,
         momentum_20d:`float$momentum_20d,
         momentum_252_skip_21:`float$momentum_252_skip_21,
         zscore_20:`float$zscore_20,
         donchian_high_20:`float$donchian_high_20,
         donchian_low_20:`float$donchian_low_20,
         donchian_breakout:`float$donchian_breakout,
         keltner_mid:`float$keltner_mid,
         keltner_upper:`float$keltner_upper,
         keltner_lower:`float$keltner_lower,
         gap_return:`float$gap_return,
         intraday_return:`float$intraday_return,
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
                                  return_1d:last return_1d,
                                  return_5d:last return_5d,
                                  return_21d:last return_21d,
                                  return_63d:last return_63d,
                                  ema_12:last ema_12,
                                  ema_26:last ema_26,
                                  ema_50:last ema_50,
                                  sma_20:last sma_20,
                                  sma_50:last sma_50,
                                  sma_200:last sma_200,
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
                                  realized_vol_20:last realized_vol_20,
                                  realized_vol_63:last realized_vol_63,
                                  stoch_k:last stoch_k,
                                  stoch_d:last stoch_d,
                                  williams_r_14:last williams_r_14,
                                  cci_20:last cci_20,
                                  adx_14:last adx_14,
                                  plus_di_14:last plus_di_14,
                                  minus_di_14:last minus_di_14,
                                  obv:last obv,
                                  volume_z:last volume_z,
                                  rolling_vwap_20:last rolling_vwap_20,
                                  momentum_20d:last momentum_20d,
                                  momentum_252_skip_21:last momentum_252_skip_21,
                                  zscore_20:last zscore_20,
                                  donchian_high_20:last donchian_high_20,
                                  donchian_low_20:last donchian_low_20,
                                  donchian_breakout:last donchian_breakout,
                                  keltner_mid:last keltner_mid,
                                  keltner_upper:last keltner_upper,
                                  keltner_lower:last keltner_lower,
                                  gap_return:last gap_return,
                                  intraday_return:last intraday_return,
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
