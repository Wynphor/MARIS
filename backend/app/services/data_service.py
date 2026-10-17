"""
DataService — 数据导入与预处理

功能：
  - ingest_raw_data: Excel/CSV → JSON
  - preprocess_data: 缺失值处理、异常值检测、标准化（SSE 流式输出）
  - scrape_external_data: 外部数据采集（模拟）
"""
import pandas as pd
import json
import asyncio
import io
import sys
import re
from pathlib import Path
from typing import Dict, AsyncGenerator
from ..core.config import settings

# Windows 控制台编码修复
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass


class DataService:

    @staticmethod
    def ingest_raw_data(workspace_id: str, file_name: str) -> Dict:
        """将原始文件（Excel/CSV）转换为标准 JSON。"""
        raw_path = settings.DATA_DIR / workspace_id / "raw" / file_name
        output_path = settings.DATA_DIR / workspace_id / "c_data.json"

        if not raw_path.exists():
            return {"status": "error", "message": f"文件不存在: {raw_path}"}

        try:
            if file_name.endswith(('.xlsx', '.xls')):
                df = pd.read_excel(raw_path)
            elif file_name.endswith('.csv'):
                df = pd.read_csv(raw_path)
            else:
                return {"status": "error", "message": f"不支持的格式: {file_name}"}

            data_list = df.to_dict(orient='records')
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data_list, f, indent=4, ensure_ascii=False)

            return {
                "status": "success",
                "rows": len(data_list),
                "fields": list(df.columns),
                "output": "c_data.json",
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    @staticmethod
    async def preprocess_data(
        workspace_id: str,
        file_name: str = None,
    ) -> AsyncGenerator[str, None]:
        """
        数据预处理流程（SSE 流式输出）：
          1. 加载数据
          2. 缺失值检测与处理
          3. 异常值检测
          4. 标准化/归一化
          5. 输出清洗后数据和报告
        """
        ws_path = settings.DATA_DIR / workspace_id

        # 1. 定位数据文件
        if file_name:
            data_file = ws_path / "raw" / file_name
        else:
            # 尝试自动查找
            for candidate in ["c_data.json", "data.xlsx", "data.csv"]:
                p = ws_path / "raw" / candidate
                if p.exists():
                    data_file = p
                    file_name = candidate
                    break
                p = ws_path / candidate
                if p.exists():
                    data_file = p
                    file_name = candidate
                    break
            else:
                yield "data: [ERROR] 未找到数据文件。请指定 file_name 或上传数据到 raw/ 目录。\n\n"
                return

        yield f"data: [INFO] 加载数据: {data_file}\n\n"

        # 加载数据
        try:
            if file_name.endswith(('.xlsx', '.xls')):
                df = pd.read_excel(data_file)
            elif file_name.endswith('.csv'):
                df = pd.read_csv(data_file)
            elif file_name.endswith('.json'):
                df = pd.read_json(data_file)
            else:
                yield f"data: [ERROR] 不支持的格式: {file_name}\n\n"
                return
        except Exception as e:
            yield f"data: [ERROR] 加载失败: {str(e)}\n\n"
            return

        yield f"data: [INFO] 数据维度: {df.shape[0]} 行 x {df.shape[1]} 列\n\n"
        yield f"data: [INFO] 字段: {', '.join(df.columns.tolist())}\n\n"

        report = {
            "file": file_name,
            "rows": df.shape[0],
            "columns": df.shape[1],
            "fields": {},
            "missing_values": {},
            "outliers": {},
            "standardization": {},
        }

        # 2. 缺失值检测与处理
        yield f"data: [STEP 2] 缺失值检测...\n\n"
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        categorical_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()

        missing_info = {}
        for col in df.columns:
            missing_count = df[col].isna().sum()
            if missing_count > 0:
                missing_rate = missing_count / len(df) * 100
                missing_info[col] = {
                    "count": int(missing_count),
                    "rate": f"{missing_rate:.1f}%",
                }

                if missing_rate < 5:
                    if col in numeric_cols:
                        fill_val = df[col].median()
                        df[col] = df[col].fillna(fill_val)
                        missing_info[col]["action"] = f"中位数填充 ({fill_val:.2f})"
                    else:
                        fill_val = df[col].mode()[0] if not df[col].mode().empty else "未知"
                        df[col] = df[col].fillna(fill_val)
                        missing_info[col]["action"] = f"众数填充 ({fill_val})"
                elif missing_rate < 20:
                    if col in numeric_cols:
                        fill_val = df[col].mean()
                        df[col] = df[col].fillna(fill_val)
                        missing_info[col]["action"] = f"均值填充 ({fill_val:.2f})"
                    else:
                        df[col] = df[col].fillna("未知")
                        missing_info[col]["action"] = "填充为'未知'"
                else:
                    missing_info[col]["action"] = "标记警告，建议人工处理"

                yield f"data: [MISSING] {col}: {missing_count}个 ({missing_rate:.1f}%) -> {missing_info[col]['action']}\n\n"

        if not missing_info:
            yield "data: [INFO] 无缺失值。\n\n"
        report["missing_values"] = missing_info

        # 3. 异常值检测
        yield f"data: [STEP 3] 异常值检测 (IQR 法)...\n\n"
        outlier_info = {}
        for col in numeric_cols:
            Q1 = df[col].quantile(0.25)
            Q3 = df[col].quantile(0.75)
            IQR = Q3 - Q1
            lower = Q1 - 1.5 * IQR
            upper = Q3 + 1.5 * IQR
            outlier_mask = (df[col] < lower) | (df[col] > upper)
            outlier_count = outlier_mask.sum()

            if outlier_count > 0:
                # Winsorize（截断到边界值）
                df[col] = df[col].clip(lower, upper)
                outlier_info[col] = {
                    "count": int(outlier_count),
                    "range": f"[{lower:.2f}, {upper:.2f}]",
                    "action": "截断到边界值 (winsorize)",
                }
                yield f"data: [OUTLIER] {col}: {outlier_count}个异常值 -> 截断到 [{lower:.2f}, {upper:.2f}]\n\n"

        if not outlier_info:
            yield "data: [INFO] 无异常值。\n\n"
        report["outliers"] = outlier_info

        # 4. 标准化
        yield f"data: [STEP 4] 标准化 (Z-score)...\n\n"
        std_info = {}
        for col in numeric_cols:
            mean_val = df[col].mean()
            std_val = df[col].std()
            if std_val > 0:
                df[col] = (df[col] - mean_val) / std_val
                std_info[col] = {
                    "method": "Z-score",
                    "original_mean": f"{mean_val:.4f}",
                    "original_std": f"{std_val:.4f}",
                }
                yield f"data: [STD] {col}: Z-score (mean={mean_val:.2f}, std={std_val:.2f})\n\n"
        report["standardization"] = std_info

        # 5. 保存结果
        processed_dir = ws_path / "processed"
        processed_dir.mkdir(parents=True, exist_ok=True)
        output_csv = processed_dir / f"{Path(file_name).stem}_clean.csv"
        df.to_csv(output_csv, index=False, encoding="utf-8-sig")

        report_path = processed_dir / "preprocess_report.md"
        report_content = DataService._generate_report_markdown(report)
        report_path.write_text(report_content, encoding="utf-8")

        # ── EDA 可视化 ──
        yield f"data: [INFO] 生成 EDA 可视化图表...\n\n"
        try:
            eda_plots = DataService.generate_eda_plots(workspace_id, df)
            if eda_plots:
                yield f"data: [INFO] 生成 {len(eda_plots)} 张 EDA 图表: {', '.join(Path(p).name for p in eda_plots)}\n\n"
                report_content += "\n\n## EDA 可视化\n\n"
                for p in eda_plots:
                    report_content += f"![{Path(p).stem}]({Path(p).name})\n\n"
                report_path.write_text(report_content, encoding="utf-8")
        except Exception as e:
            yield f"data: [WARNING] EDA 图表生成失败: {str(e)}\n\n"

        # ── 字段语义描述 ──
        try:
            field_desc = DataService.generate_field_descriptions(df)
            if field_desc:
                report_content += "\n\n## 字段语义描述\n\n"
                report_content += "| 字段 | 类型 | 均值 | 范围 | 可能单位 |\n"
                report_content += "|------|------|------|------|----------|\n"
                for col, info in field_desc.items():
                    if info.get("type") == "numeric":
                        unit = info.get("possible_unit", "—")
                        report_content += f"| {col} | 数值 | {info.get('mean', '—')} | [{info.get('min', '?')}, {info.get('max', '?')}] | {unit} |\n"
                    else:
                        report_content += f"| {col} | 分类 | — | {info.get('unique_count', '?')} 类 | — |\n"
                report_path.write_text(report_content, encoding="utf-8")
        except Exception:
            pass

        yield f"data: [SUCCESS] 预处理完成。\n\n"
        yield f"data: [OUTPUT] 清洗数据: {output_csv}\n\n"
        yield f"data: [OUTPUT] 预处理报告: {report_path}\n\n"
        yield f"data: {json.dumps({'status': 'success', 'output_csv': str(output_csv), 'report': str(report_path)}, ensure_ascii=False)}\n\n"

    @staticmethod
    def _generate_report_markdown(report: dict) -> str:
        """生成 Markdown 格式的预处理报告。"""
        lines = [
            "# 数据预处理报告",
            "",
            f"## 数据概览",
            f"- 文件: {report['file']}",
            f"- 行数: {report['rows']}, 列数: {report['columns']}",
            "",
            "## 缺失值处理",
            "| 字段 | 缺失数 | 缺失率 | 处理方式 |",
            "|------|--------|--------|---------|",
        ]
        if report["missing_values"]:
            for col, info in report["missing_values"].items():
                lines.append(f"| {col} | {info['count']} | {info['rate']} | {info['action']} |")
        else:
            lines.append("| — | 0 | 0% | 无缺失 |")

        lines.extend(["", "## 异常值检测", "| 字段 | 异常值数 | 范围 | 处理方式 |", "|------|---------|------|---------|"])
        if report["outliers"]:
            for col, info in report["outliers"].items():
                lines.append(f"| {col} | {info['count']} | {info['range']} | {info['action']} |")
        else:
            lines.append("| — | 0 | — | 无异常 |")

        lines.extend(["", "## 标准化", "| 字段 | 方法 | 原始均值 | 原始标准差 |", "|------|------|---------|-----------|"])
        if report["standardization"]:
            for col, info in report["standardization"].items():
                lines.append(f"| {col} | {info['method']} | {info['original_mean']} | {info['original_std']} |")
        else:
            lines.append("| — | — | — | — |")

        return "\n".join(lines)

    @staticmethod
    def generate_eda_plots(workspace_id: str, df: pd.DataFrame) -> list:
        """
        生成 EDA 可视化图表，保存到 output/figures/。
        返回生成的图表文件路径列表。
        """
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np

        plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "DejaVu Sans"]
        plt.rcParams["axes.unicode_minus"] = False

        fig_dir = settings.DATA_DIR / workspace_id / "output" / "figures"
        fig_dir.mkdir(parents=True, exist_ok=True)
        saved = []

        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        if not numeric_cols:
            return saved

        # 1. Distribution histograms
        n_cols = min(len(numeric_cols), 8)
        n_rows = (n_cols + 3) // 4
        fig, axes = plt.subplots(n_rows, 4, figsize=(16, 4 * n_rows))
        axes = axes.flatten() if n_rows > 1 else [axes] if n_rows == 1 else axes.flatten()
        for i, col in enumerate(numeric_cols[:8]):
            ax = axes[i]
            data = df[col].dropna()
            if len(data) > 0:
                ax.hist(data, bins=30, alpha=0.7, color="#e87a35", edgecolor="white")
                ax.set_title(col[:20], fontsize=10)
                ax.tick_params(labelsize=8)
        for i in range(n_cols, len(axes)):
            axes[i].set_visible(False)
        plt.tight_layout()
        path = fig_dir / "eda_distributions.png"
        fig.savefig(str(path), dpi=120, bbox_inches="tight")
        plt.close(fig)
        saved.append(str(path))

        # 2. Correlation matrix
        if len(numeric_cols) >= 2:
            corr_cols = numeric_cols[:12]  # Limit to 12 for readability
            corr = df[corr_cols].corr()
            fig, ax = plt.subplots(figsize=(max(6, len(corr_cols)), max(5, len(corr_cols) * 0.8)))
            im = ax.imshow(corr.values, cmap="RdBu_r", vmin=-1, vmax=1, aspect="auto")
            ax.set_xticks(range(len(corr_cols)))
            ax.set_yticks(range(len(corr_cols)))
            ax.set_xticklabels([c[:15] for c in corr_cols], rotation=45, ha="right", fontsize=8)
            ax.set_yticklabels([c[:15] for c in corr_cols], fontsize=8)
            for i in range(len(corr_cols)):
                for j in range(len(corr_cols)):
                    val = corr.values[i, j]
                    ax.text(j, i, f"{val:.2f}", ha="center", va="center", fontsize=7,
                           color="white" if abs(val) > 0.5 else "black")
            plt.colorbar(im, ax=ax, shrink=0.8)
            ax.set_title("Correlation Matrix", fontsize=11)
            plt.tight_layout()
            path = fig_dir / "eda_correlation.png"
            fig.savefig(str(path), dpi=120, bbox_inches="tight")
            plt.close(fig)
            saved.append(str(path))

        # 3. Box plots (top 8 numeric columns)
        if len(numeric_cols) >= 1:
            box_cols = numeric_cols[:8]
            fig, ax = plt.subplots(figsize=(max(6, len(box_cols) * 1.2), 5))
            box_data = [df[c].dropna().values for c in box_cols]
            bp = ax.boxplot(box_data, labels=[c[:12] for c in box_cols], patch_artist=True)
            for patch in bp["boxes"]:
                patch.set_facecolor("#e87a35")
                patch.set_alpha(0.6)
            ax.set_title("Box Plots", fontsize=11)
            ax.tick_params(labelsize=8)
            plt.xticks(rotation=30, ha="right")
            plt.tight_layout()
            path = fig_dir / "eda_boxplots.png"
            fig.savefig(str(path), dpi=120, bbox_inches="tight")
            plt.close(fig)
            saved.append(str(path))

        # 4. Scatter matrix (top 4 numeric columns)
        if len(numeric_cols) >= 2:
            scatter_cols = numeric_cols[:4]
            n = len(scatter_cols)
            fig, axes = plt.subplots(n, n, figsize=(3 * n, 3 * n))
            if n == 1:
                axes = np.array([[axes]])
            for i in range(n):
                for j in range(n):
                    ax = axes[i][j]
                    if i == j:
                        ax.hist(df[scatter_cols[i]].dropna(), bins=20, alpha=0.7, color="#e87a35")
                    else:
                        ax.scatter(df[scatter_cols[j]], df[scatter_cols[i]], alpha=0.3, s=5, color="#e87a35")
                    if i == n - 1:
                        ax.set_xlabel(scatter_cols[j][:10], fontsize=8)
                    if j == 0:
                        ax.set_ylabel(scatter_cols[i][:10], fontsize=8)
                    ax.tick_params(labelsize=7)
            plt.suptitle("Scatter Matrix", fontsize=11)
            plt.tight_layout()
            path = fig_dir / "eda_scatter_matrix.png"
            fig.savefig(str(path), dpi=120, bbox_inches="tight")
            plt.close(fig)
            saved.append(str(path))

        return saved

    @staticmethod
    def generate_field_descriptions(df: pd.DataFrame) -> dict:
        """
        生成字段语义描述（类型推断、统计摘要、可能的单位）。
        """
        import numpy as np
        desc = {}
        for col in df.columns:
            info = {"dtype": str(df[col].dtype), "non_null": int(df[col].notna().sum())}
            if df[col].dtype in ("float64", "int64", "float32", "int32"):
                stats = df[col].describe()
                info["mean"] = round(float(stats["mean"]), 4) if not np.isnan(stats["mean"]) else None
                info["std"] = round(float(stats["std"]), 4) if not np.isnan(stats["std"]) else None
                info["min"] = round(float(stats["min"]), 4)
                info["max"] = round(float(stats["max"]), 4)
                info["type"] = "numeric"
                # Heuristic unit detection
                col_lower = col.lower()
                if any(k in col_lower for k in ("率", "ratio", "pct", "percent", "%")):
                    info["possible_unit"] = "%" if info["max"] <= 100 else "ratio(0-1)"
                elif any(k in col_lower for k in ("年", "year", "age")):
                    info["possible_unit"] = "年"
                elif any(k in col_lower for k in ("gdp", "收入", "income", "产值", "金额")):
                    info["possible_unit"] = "万元/亿元"
                elif any(k in col_lower for k in ("温度", "temp")):
                    info["possible_unit"] = "°C"
                elif any(k in col_lower for k in ("面积", "area", "距离", "dist", "长度")):
                    info["possible_unit"] = "km²/km"
            else:
                info["type"] = "categorical"
                info["unique_count"] = int(df[col].nunique())
                top = df[col].value_counts().head(3)
                info["top_values"] = {str(k): int(v) for k, v in top.items()}
            desc[col] = info
        return desc

    @staticmethod
    async def scrape_external_data(workspace_id: str, query: str, source: str = "general") -> AsyncGenerator[str, None]:
        """
        外部数据采集。

        支持的数据源:
          - worldbank: 世界银行公开数据 API
          - general: 通用网络搜索 + LLM 结构化提取
        """
        yield f"data: [INFO] 正在搜索外部数据: '{query}' (来源: {source})...\n\n"

        ws_path = settings.DATA_DIR / workspace_id / "raw"
        ws_path.mkdir(parents=True, exist_ok=True)

        results = []
        source_urls = []  # Track actual URLs used

        # ── Source 1: World Bank API ──
        if source in ("worldbank", "general"):
            yield f"data: [INFO] 查询世界银行 API...\n\n"
            try:
                import httpx
                # Search for indicators matching the query
                search_url = f"https://api.worldbank.org/v2/indicator?format=json&per_page=5&q={query}"
                source_urls.append(search_url)
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.get(search_url)
                    if resp.status_code == 200:
                        data = resp.json()
                        if len(data) > 1 and data[1]:
                            indicators = data[1][:3]  # Top 3 matching indicators
                            for ind in indicators:
                                ind_id = ind.get("id", "")
                                ind_name = ind.get("name", "")
                                yield f"data: [INFO] 找到指标: {ind_name} ({ind_id})...\n\n"

                                # Fetch indicator data (China, 2015-2023)
                                data_url = f"https://api.worldbank.org/v2/country/CHN/indicator/{ind_id}?format=json&date=2015:2023&per_page=20"
                                source_urls.append(data_url)
                                data_resp = await client.get(data_url)
                                if data_resp.status_code == 200:
                                    ind_data = data_resp.json()
                                    if len(ind_data) > 1 and ind_data[1]:
                                        for item in ind_data[1]:
                                            if item.get("value") is not None:
                                                results.append({
                                                    "source": "World Bank",
                                                    "source_url": data_url,
                                                    "indicator": ind_name,
                                                    "indicator_id": ind_id,
                                                    "country": "China",
                                                    "year": item.get("date", ""),
                                                    "value": item.get("value"),
                                                })
            except ImportError:
                yield "data: [WARNING] httpx 未安装，无法查询世界银行 API。\n\n"
            except Exception as e:
                yield f"data: [WARNING] 世界银行 API 查询失败: {str(e)}\n\n"

        # ── Source 2: Open data APIs (NBS/IMF/OECD) ──
        if source in ("national", "stats", "imf", "oecd", "general") and not results:
            yield f"data: [INFO] 查询公开数据 API...\n\n"
            try:
                import httpx
                async with httpx.AsyncClient(timeout=30) as client:
                    # IMF Data API (free, no key required)
                    if source in ("imf", "general"):
                        yield f"data: [INFO] 查询 IMF 数据...\n\n"
                        imf_url = f"https://www.imf.org/external/datamapper/api/v1/NGDP_RPCH?periods=2015,2016,2017,2018,2019,2020,2021,2022,2023"
                        source_urls.append(imf_url)
                        try:
                            resp = await client.get(imf_url)
                            if resp.status_code == 200:
                                imf_data = resp.json()
                                if isinstance(imf_data, dict):
                                    for indicator, countries in imf_data.items():
                                        if isinstance(countries, dict):
                                            for country, years in countries.items():
                                                if isinstance(years, dict) and country == "CHN":
                                                    for year, val in years.items():
                                                        if val is not None:
                                                            results.append({
                                                                "source": "IMF",
                                                                "source_url": imf_url,
                                                                "indicator": indicator,
                                                                "country": country,
                                                                "year": str(year),
                                                                "value": val,
                                                            })
                        except Exception:
                            pass

                    # OECD Data API (free, no key)
                    if source in ("oecd", "general") and not results:
                        yield f"data: [INFO] 查询 OECD 数据...\n\n"
                        oecd_url = f"https://sdmx.oecd.org/public/rest/data/OECD.SDD.NAS,DSD_NAMAIN1@DF_TABLE1,1.0/CHN.B1_GE.GY.Q?startPeriod=2015&endPeriod=2023"
                        source_urls.append(oecd_url)
                        try:
                            resp = await client.get(oecd_url, headers={"Accept": "application/json"})
                            if resp.status_code == 200:
                                oecd_data = resp.json()
                                # Parse SDMX-JSON structure
                                if "dataSets" in oecd_data:
                                    for ds in oecd_data["dataSets"]:
                                        for series_key, series in ds.get("series", {}).items():
                                            for obs_key, obs in series.get("observations", {}).items():
                                                if obs and len(obs) > 0:
                                                    results.append({
                                                        "source": "OECD",
                                                        "source_url": oecd_url,
                                                        "indicator": "GDP Growth",
                                                        "country": "CHN",
                                                        "year": str(2015 + int(obs_key)) if obs_key.isdigit() else obs_key,
                                                        "value": obs[0] if isinstance(obs, list) else obs,
                                                    })
                        except Exception:
                            pass

                    # NBS China (data.stats.gov.cn)
                    if source in ("national", "stats", "general") and not results:
                        yield f"data: [INFO] 查询国家统计局数据...\n\n"
                        # Multiple NBS indicator codes
                        nbs_codes = {
                            "adb4ca77a4634c05a35619a1fa3e1e4d": "GDP",
                            "af167e9a03594166a3b2104354ab8ef8": "Population",
                            "a1a45ae4d05d434587e65d2432e64bc0": "CPI",
                        }
                        for code, name in nbs_codes.items():
                            if results:
                                break
                            nbs_url = f"https://data.stats.gov.cn/english/tablequery.htm?m=QueryData&code={code}"
                            source_urls.append(nbs_url)
                            try:
                                resp = await client.get(nbs_url)
                                if resp.status_code == 200:
                                    nbs_data = resp.json()
                                    if isinstance(nbs_data, dict) and "returndata" in nbs_data:
                                        for item in nbs_data["returndata"].get("datanodes", [])[:30]:
                                            if item.get("data", {}).get("hasdata"):
                                                wds = item.get("wds", [])
                                                results.append({
                                                    "source": f"National Bureau of Statistics ({name})",
                                                    "source_url": nbs_url,
                                                    "indicator": wds[0].get("cname", name) if wds else name,
                                                    "year": wds[1].get("cname", "") if len(wds) > 1 else "",
                                                    "value": item["data"].get("data", 0),
                                                })
                            except Exception:
                                pass
            except Exception as e:
                yield f"data: [WARNING] 公开数据 API 查询失败: {str(e)}\n\n"

        # ── Source 3: General web search via LLM ──
        if source == "general" or not results:
            yield f"data: [INFO] 使用 AI 分析数据需求并生成结构化数据...\n\n"
            try:
                from ..services.api_client_service import APIClientService
                from ..core.prompts import build_stage_system_prompt

                data_system = (
                    "你是数据分析专家。根据用户的数据需求，生成一组合理的结构化数据。\n"
                    "输出格式：JSON 数组，每个元素包含 year, indicator, value, source 字段。\n"
                    "数据应基于真实公开统计口径（注明来源），10-20 条记录。\n"
                    "只输出 JSON，不要其他内容。"
                )
                data_user = f"数据需求: {query}\n数据来源偏好: {source}\n\n请生成结构化数据集（JSON 数组）。"

                collected = ""
                async for chunk in APIClientService.call_llm(
                    system=data_system,
                    user=data_user,
                    temperature=0.3,
                ):
                    collected += chunk

                # Extract JSON from response
                import re
                json_match = re.search(r'\[[\s\S]*\]', collected)
                if json_match:
                    try:
                        llm_data = json.loads(json_match.group())
                        if isinstance(llm_data, list):
                            for item in llm_data:
                                item.setdefault("source", "AI Generated")
                                item.setdefault("source_url", "")
                            results.extend(llm_data)
                            yield f"data: [INFO] AI 生成了 {len(llm_data)} 条数据记录。\n\n"
                    except json.JSONDecodeError:
                        yield "data: [WARNING] AI 返回的数据格式无效。\n\n"
            except Exception as e:
                yield f"data: [WARNING] AI 数据生成失败: {str(e)}\n\n"

        # ── Save results with evidence metadata ──
        if results:
            safe_name = re.sub(r'[^\w\-]', '_', query[:30]).strip('_')
            out_file = ws_path / f"scraped_{safe_name}.json"

            # Build field definitions from actual data keys
            all_keys = set()
            for r in results:
                all_keys.update(r.keys())
            field_defs = {}
            for k in sorted(all_keys):
                sample_vals = [r.get(k) for r in results[:5] if r.get(k) is not None]
                ftype = "string"
                if sample_vals:
                    if all(isinstance(v, (int, float)) for v in sample_vals):
                        ftype = "number"
                    elif all(isinstance(v, bool) for v in sample_vals):
                        ftype = "boolean"
                field_defs[k] = {"type": ftype, "description": k}

            # Build evidence envelope
            from datetime import datetime
            envelope = {
                "metadata": {
                    "query": query,
                    "source_type": source,
                    "download_time": datetime.now().isoformat(),
                    "record_count": len(results),
                    "source_urls": list(set(source_urls)),
                    "sources_used": list(set(r.get("source", "unknown") for r in results)),
                    "field_definitions": field_defs,
                    "provenance": {
                        "worldbank_api": source in ("worldbank", "general"),
                        "ai_generated": any(r.get("source") == "AI Generated" for r in results),
                        "note": "AI Generated 数据仅作参考，不能作为论文证据。World Bank 数据可引用。"
                    },
                    "workspace_id": workspace_id,
                },
                "records": results,
            }

            with open(out_file, 'w', encoding='utf-8') as f:
                json.dump(envelope, f, indent=2, ensure_ascii=False)
            yield f"data: [SUCCESS] 共采集 {len(results)} 条记录，保存到 raw/{out_file.name}\n\n"
            yield f"data: [INFO] 数据来源: {', '.join(envelope['metadata']['sources_used'])}\n\n"
            if envelope["metadata"]["provenance"]["ai_generated"]:
                yield "data: [WARNING] 包含 AI 生成数据，仅供探索参考。论文中请使用有明确来源的数据。\n\n"
                # 在数据文件中标记 AI 数据不可引用
                envelope["metadata"]["provenance"]["citation_blocked"] = True
                envelope["metadata"]["provenance"]["block_reason"] = "AI Generated data cannot be cited in academic papers"
                # 重新写入带阻止标记的文件
                with open(out_file, 'w', encoding='utf-8') as f:
                    json.dump(envelope, f, indent=2, ensure_ascii=False)
        else:
            yield "data: [WARNING] 未能采集到数据。请检查查询关键词或手动提供数据文件。\n\n"
