import sys
import os

# bare import들(agent, agent_executor 등)이 pytest 환경에서도 동작하도록 경로 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
