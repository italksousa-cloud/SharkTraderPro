import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px
from datetime import datetime
import webbrowser
import os
from database import DatabaseManager
from logger_setup import logger

class TradingDashboard:
    def __init__(self, db: DatabaseManager):
        self.db = db
        # Load all trades
        with self.db._get_connection() as conn:
            self.df_trades = pd.read_sql_query("SELECT * FROM trades_history", conn)
            
        if not self.df_trades.empty:
            self.df_trades['entry_time'] = pd.to_datetime(self.df_trades['entry_time'])
            self.df_trades['exit_time'] = pd.to_datetime(self.df_trades['exit_time'])
            
            # Helper columns
            self.df_trades['date'] = self.df_trades['entry_time'].dt.date
            self.df_trades['hour'] = self.df_trades['entry_time'].dt.hour
            self.df_trades['weekday'] = self.df_trades['entry_time'].dt.day_name()
            self.df_trades['month'] = self.df_trades['entry_time'].dt.strftime('%Y-%m')

    def plot_equity_curve_by_timeframe(self):
        if self.df_trades.empty: return go.Figure()
        
        fig = go.Figure()
        colors = {'15m': 'blue', '1h': 'green', '4h': 'orange', '1d': 'purple'}
        
        for tf in ['15m', '1h', '4h', '1d']:
            df_tf = self.df_trades[self.df_trades['timeframe'] == tf].copy()
            if df_tf.empty: continue
            
            df_tf = df_tf.sort_values('exit_time')
            df_tf['cum_profit'] = df_tf['profit_loss'].cumsum()
            
            fig.add_trace(go.Scatter(
                x=df_tf['exit_time'], y=df_tf['cum_profit'],
                mode='lines', name=f'TF: {tf}',
                line=dict(color=colors.get(tf, 'gray'), width=2)
            ))
            
        fig.update_layout(title="Equity Curve por Timeframe", xaxis_title="Time", yaxis_title="Cumulative PnL ($)")
        return fig

    def plot_winrate_by_timeframe(self):
        if self.df_trades.empty: return go.Figure()
        
        stats = []
        for tf in ['15m', '1h', '4h', '1d']:
            df_tf = self.df_trades[self.df_trades['timeframe'] == tf]
            if df_tf.empty:
                stats.append({'tf': tf, 'wr': 0})
                continue
            wins = len(df_tf[df_tf['result'] == 'win'])
            wr = (wins / len(df_tf)) * 100
            stats.append({'tf': tf, 'wr': wr})
            
        df_stats = pd.DataFrame(stats)
        
        colors = ['red' if w < 50 else ('orange' if w < 60 else 'green') for w in df_stats['wr']]
        
        fig = go.Figure(data=[go.Bar(
            x=df_stats['tf'], y=df_stats['wr'],
            marker_color=colors,
            text=[f"{w:.1f}%" for w in df_stats['wr']],
            textposition='auto'
        )])
        fig.add_hline(y=50, line_dash="dash", line_color="black")
        fig.update_layout(title="Win Rate por Timeframe", yaxis_title="Win Rate (%)")
        return fig

    def plot_profit_by_timeframe(self):
        if self.df_trades.empty: return go.Figure()
        
        stats = []
        for tf in ['15m', '1h', '4h', '1d']:
            df_tf = self.df_trades[self.df_trades['timeframe'] == tf]
            pnl = df_tf['profit_loss'].sum() if not df_tf.empty else 0
            stats.append({'tf': tf, 'pnl': pnl})
            
        df_stats = pd.DataFrame(stats)
        colors = ['green' if p >= 0 else 'red' for p in df_stats['pnl']]
        
        fig = go.Figure(data=[go.Bar(
            x=df_stats['tf'], y=df_stats['pnl'],
            marker_color=colors,
            text=[f"${p:.2f}" for p in df_stats['pnl']],
            textposition='auto'
        )])
        fig.update_layout(title="Lucro Total por Timeframe", yaxis_title="PnL ($)")
        return fig

    def plot_trades_count_by_timeframe(self):
        if self.df_trades.empty: return go.Figure()
        
        wins = []
        losses = []
        tfs = ['15m', '1h', '4h', '1d']
        
        for tf in tfs:
            df_tf = self.df_trades[self.df_trades['timeframe'] == tf]
            wins.append(len(df_tf[df_tf['result'] == 'win']))
            losses.append(len(df_tf[df_tf['result'] == 'loss']))
            
        fig = go.Figure(data=[
            go.Bar(name='Wins', x=tfs, y=wins, marker_color='green'),
            go.Bar(name='Losses', x=tfs, y=losses, marker_color='red')
        ])
        fig.update_layout(barmode='stack', title="Número de Trades por Timeframe")
        return fig

    def plot_drawdown_by_timeframe(self):
        # Simplified drawdown approximation
        if self.df_trades.empty: return go.Figure()
        
        fig = go.Figure()
        for tf in ['15m', '1h', '4h', '1d']:
            df_tf = self.df_trades[self.df_trades['timeframe'] == tf].copy()
            if df_tf.empty: continue
            
            df_tf = df_tf.sort_values('exit_time')
            df_tf['cum_profit'] = df_tf['profit_loss'].cumsum()
            df_tf['peak_profit'] = df_tf['cum_profit'].cummax()
            df_tf['drawdown'] = df_tf['cum_profit'] - df_tf['peak_profit']
            
            fig.add_trace(go.Scatter(
                x=df_tf['exit_time'], y=df_tf['drawdown'],
                mode='lines', name=f'{tf}', fill='tozeroy'
            ))
            
        fig.update_layout(title="Drawdown por Timeframe", yaxis_title="Drawdown ($)")
        return fig

    def plot_profit_factor_by_timeframe(self):
        if self.df_trades.empty: return go.Figure()
        
        stats = []
        for tf in ['15m', '1h', '4h', '1d']:
            df_tf = self.df_trades[self.df_trades['timeframe'] == tf]
            gross_p = df_tf[df_tf['profit_loss'] > 0]['profit_loss'].sum()
            gross_l = abs(df_tf[df_tf['profit_loss'] < 0]['profit_loss'].sum())
            pf = gross_p / gross_l if gross_l > 0 else (float('inf') if gross_p > 0 else 0)
            stats.append({'tf': tf, 'pf': pf if pf != float('inf') else 5.0}) # Cap at 5 for plot
            
        df_stats = pd.DataFrame(stats)
        colors = ['red' if p < 1 else ('orange' if p < 1.5 else 'green') for p in df_stats['pf']]
        
        fig = go.Figure(data=[go.Bar(
            x=df_stats['tf'], y=df_stats['pf'],
            marker_color=colors,
            text=[f"{p:.2f}" for p in df_stats['pf']],
            textposition='auto'
        )])
        fig.add_hline(y=1.0, line_dash="dash", line_color="black")
        fig.update_layout(title="Profit Factor por Timeframe")
        return fig

    def plot_avg_trade_by_timeframe(self):
        if self.df_trades.empty: return go.Figure()
        
        avg_w = []
        avg_l = []
        tfs = ['15m', '1h', '4h', '1d']
        
        for tf in tfs:
            df_tf = self.df_trades[self.df_trades['timeframe'] == tf]
            aw = df_tf[df_tf['profit_loss'] > 0]['profit_loss'].mean()
            al = df_tf[df_tf['profit_loss'] < 0]['profit_loss'].mean()
            avg_w.append(aw if not pd.isna(aw) else 0)
            avg_l.append(abs(al) if not pd.isna(al) else 0)
            
        fig = go.Figure(data=[
            go.Bar(name='Avg Win (+)', x=tfs, y=avg_w, marker_color='green'),
            go.Bar(name='Avg Loss (-)', x=tfs, y=[-x for x in avg_l], marker_color='red')
        ])
        fig.update_layout(barmode='group', title="Avg Win vs Avg Loss")
        return fig

    def get_best_timeframe(self):
        if self.df_trades.empty: return {"best": "N/A", "score": 0}
        
        scores = {}
        for tf in ['15m', '1h', '4h', '1d']:
            df_tf = self.df_trades[self.df_trades['timeframe'] == tf]
            if len(df_tf) < 5: 
                scores[tf] = 0
                continue
                
            wins = len(df_tf[df_tf['result'] == 'win'])
            wr = (wins / len(df_tf)) * 100
            pnl = df_tf['profit_loss'].sum()
            
            gross_p = df_tf[df_tf['profit_loss'] > 0]['profit_loss'].sum()
            gross_l = abs(df_tf[df_tf['profit_loss'] < 0]['profit_loss'].sum())
            pf = gross_p / gross_l if gross_l > 0 else (5.0 if gross_p > 0 else 0)
            
            score = (wr * 0.4) + (min(pf, 3) * 10) + (10 if pnl > 0 else -10)
            scores[tf] = score
            
        best_tf = max(scores, key=scores.get) if scores else "N/A"
        return {"best": best_tf, "score": scores.get(best_tf, 0)}

    def plot_heatmap_hourly(self):
        if self.df_trades.empty: return go.Figure()
        
        heatmap_data = self.df_trades.pivot_table(
            values='profit_loss', 
            index='weekday', 
            columns='hour', 
            aggfunc='mean'
        ).fillna(0)
        
        weekdays_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        heatmap_data = heatmap_data.reindex(weekdays_order)
        
        fig = px.imshow(
            heatmap_data,
            labels=dict(x="Hour of Day", y="Day of Week", color="Avg PnL"),
            x=heatmap_data.columns,
            y=heatmap_data.index,
            color_continuous_scale="RdYlGn"
        )
        fig.update_layout(title="Heatmap: PnL Médio por Hora/Dia")
        return fig

    def generate_full_dashboard(self, save_html=True):
        logger.info("Generating full dashboard...")
        
        if self.df_trades.empty:
            logger.warning("No trades available to generate dashboard.")
            return

        with open("dashboard.html", "w", encoding='utf-8') as f:
            f.write("<html><head><title>Shark Trader Pro Dashboard</title></head><body>")
            f.write("<h1>🦈 Shark Trader Pro - Performance Dashboard</h1>")
            
            best_info = self.get_best_timeframe()
            f.write(f"<h2>Melhor Timeframe: {best_info['best']} (Score: {best_info['score']:.1f})</h2>")
            
            f.write("<h3>Equity Curves</h3>")
            f.write(self.plot_equity_curve_by_timeframe().to_html(full_html=False, include_plotlyjs='cdn'))
            
            f.write("<h3>Comparativo de Timeframes</h3>")
            f.write(self.plot_winrate_by_timeframe().to_html(full_html=False, include_plotlyjs=False))
            f.write(self.plot_profit_by_timeframe().to_html(full_html=False, include_plotlyjs=False))
            f.write(self.plot_profit_factor_by_timeframe().to_html(full_html=False, include_plotlyjs=False))
            f.write(self.plot_avg_trade_by_timeframe().to_html(full_html=False, include_plotlyjs=False))
            f.write(self.plot_trades_count_by_timeframe().to_html(full_html=False, include_plotlyjs=False))
            f.write(self.plot_drawdown_by_timeframe().to_html(full_html=False, include_plotlyjs=False))
            
            f.write("<h3>Heatmaps Horários</h3>")
            f.write(self.plot_heatmap_hourly().to_html(full_html=False, include_plotlyjs=False))
            
            f.write("</body></html>")
            
        logger.info("Dashboard HTML generated successfully.")
        
        if save_html:
            abs_path = os.path.abspath("dashboard.html")
            webbrowser.open(f'file://{abs_path}')

    def print_terminal_summary(self):
        os.system("cls" if os.name == "nt" else "clear")
        best = self.get_best_timeframe()
        
        print("┌" + "─" * 47 + "┐")
        print("│  🦈 SHARK TRADER PRO - PERFORMANCE DASHBOARD  │")
        print("├" + "─" * 47 + "┤")
        print(f"│  MELHOR TIMEFRAME: {best['best']:<2} (Score: {best['score']:.1f})             │")
        print("│  ──────────────────────────────────────────   │")
        print("│  TF    | Trades | WR%  | PnL $   | PF         │")
        
        total_pnl = 0
        for tf in ['15m', '1h', '4h', '1d']:
            df_tf = self.df_trades[self.df_trades['timeframe'] == tf] if not self.df_trades.empty else pd.DataFrame()
            if df_tf.empty:
                print(f"│  {tf:<5} |   0    | 0%   | $0      | 0.0        │")
                continue
                
            trades = len(df_tf)
            wr = (len(df_tf[df_tf['result'] == 'win']) / trades) * 100
            pnl = df_tf['profit_loss'].sum()
            total_pnl += pnl
            
            gross_p = df_tf[df_tf['profit_loss'] > 0]['profit_loss'].sum()
            gross_l = abs(df_tf[df_tf['profit_loss'] < 0]['profit_loss'].sum())
            pf = gross_p / gross_l if gross_l > 0 else (5.0 if gross_p > 0 else 0.0)
            
            best_mark = "← BEST" if tf == best['best'] else ""
            sign = "+" if pnl >= 0 else ""
            print(f"│  {tf:<5} |   {trades:<4} | {wr:.0f}%  | {sign}${abs(pnl):<6.2f} | {pf:.1f} {best_mark:<8}│")
            
        print("│  ──────────────────────────────────────────   │")
        
        # Hoje, Semana, Mes logic
        hoje = pd.Timestamp('today').date()
        mes_atual = pd.Timestamp('today').strftime('%Y-%m')
        
        pnl_hoje = self.df_trades[self.df_trades['date'] == hoje]['profit_loss'].sum() if not self.df_trades.empty else 0
        pnl_mes = self.df_trades[self.df_trades['month'] == mes_atual]['profit_loss'].sum() if not self.df_trades.empty else 0
        
        s_hoje = "+" if pnl_hoje >= 0 else ""
        s_mes = "+" if pnl_mes >= 0 else ""
        
        print(f"│  HOJE: {s_hoje}${abs(pnl_hoje):.2f} | MÊS: {s_mes}${abs(pnl_mes):.2f}                     │")
        print("└" + "─" * 47 + "┘")
