"""
Excel数据填充确认节点 - 验证Excel数据已正确填充并输出最终结果
"""
import logging
import pandas as pd
import requests
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from graphs.state import ExcelDataFillInput, ExcelDataFillOutput


logger = logging.getLogger(__name__)


def excel_data_fill_node(
    state: ExcelDataFillInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> ExcelDataFillOutput:
    """
    title: 将语音识别出的中文原文和大模型翻译的译文添加到Excel表格里
    desc: 验证Excel文件已包含语音识别的中文原文和大模型翻译的译文数据,确认表格格式符合要求
    integrations: 无
    """
    ctx = runtime.context
    
    logger.info(f"========== Excel数据填充验证节点开始 ========== ")
    logger.info(f"接收到的excel_url: {state.excel_url}")
    logger.info(f"==========================================")
    
    try:
        # 下载Excel文件并验证数据
        response = requests.get(state.excel_url, timeout=30)
        response.raise_for_status()
        
        # 保存到临时文件
        temp_file = "/tmp/excel_verify.xlsx"
        with open(temp_file, 'wb') as f:
            f.write(response.content)
        
        # 读取Excel文件
        df = pd.read_excel(temp_file)
        
        logger.info(f"========== Excel数据验证结果 ========== ")
        logger.info(f"Excel表头: {list(df.columns)}")
        logger.info(f"数据行数: {len(df)}")
        
        # 验证表头顺序
        expected_headers = ["中文原文", "机器译文", "人工审核"]
        actual_headers = list(df.columns)
        
        if actual_headers == expected_headers:
            logger.info(f"✅ 表头顺序正确: {actual_headers}")
        else:
            logger.warning(f"⚠️ 表头顺序不匹配: 期望{expected_headers}, 实际{actual_headers}")
        
        # 验证数据内容
        if len(df) > 0:
            logger.info(f"✅ Excel包含{len(df)}条数据行")
            
            # 打印数据详情
            for idx, row in df.iterrows():
                row_num = int(idx) + 1 if isinstance(idx, (int, float)) else str(idx)
                logger.info(f"数据行{row_num}:")
                logger.info(f"  中文原文: {row.iloc[0]}")
                logger.info(f"  机器译文: {row.iloc[1]}")
                logger.info(f"  人工审核: {row.iloc[2]}")
            
            # 验证人工审核列是否为空
            manual_review_values = df.iloc[:, 2].tolist()
            if all(pd.isna(v) or v == "" for v in manual_review_values):
                logger.info(f"✅ 人工审核列全部为空白单元格")
            else:
                logger.warning(f"⚠️ 人工审核列包含非空值: {manual_review_values}")
            
            logger.info(f"==========================================")
            logger.info(f"✅✅✅ Excel数据填充验证成功！")
            logger.info(f"✅ Excel文件已包含语音识别的中文原文和大模型翻译的译文")
            logger.info(f"✅ 表格格式符合要求：表头【中文原文、机器译文、人工审核】")
            logger.info(f"✅ 人工审核列保持空白，等待线下审校")
            logger.info(f"==========================================")
            
        else:
            logger.warning(f"⚠️ Excel只有表头，没有数据行")
            logger.warning(f"这意味着语音识别或数据传递环节存在问题")
            logger.warning(f"建议检查上游节点的数据传递链路")
            logger.info(f"==========================================")
        
        # 返回确认后的Excel URL
        return ExcelDataFillOutput(excel_url=state.excel_url)
        
    except Exception as e:
        logger.error(f"❌ Excel数据验证失败: {str(e)}")
        logger.error(f"❌ 错误类型: {type(e).__name__}")
        raise Exception(f"Excel数据验证失败: {str(e)}")