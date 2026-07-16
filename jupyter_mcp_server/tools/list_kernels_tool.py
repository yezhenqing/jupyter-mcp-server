# Copyright (c) 2024- Datalayer, Inc.
#
# BSD 3-Clause License

"""List all available kernel specs and active kernels tool."""

from typing import Any, Optional, List, Dict
from jupyter_server_client import JupyterServerClient

from jupyter_mcp_server.tools._base import BaseTool, ServerMode
from jupyter_mcp_server.utils import format_TSV


class ListKernelsTool(BaseTool):
    """List all available kernel specs and currently active kernels in the Jupyter server."""

    def _get_kernels_info_http(
        self, server_client: JupyterServerClient
    ) -> tuple[List[Dict[str, str]], List[Dict[str, str]]]:
        """Fetch active kernels and available specs using HTTP API (MCP_SERVER mode)."""
        try:
            # 1. Fetch Available Kernel Specs
            available_specs = []
            kernels_specs = server_client.kernelspecs.list_kernelspecs()
            
            specs_dict = getattr(kernels_specs, 'kernelspecs', {}) or {}
            for name, spec_obj in specs_dict.items():
                spec = getattr(spec_obj, 'spec', spec_obj)
                
                display_name = getattr(spec, 'display_name', name) if hasattr(spec, 'display_name') else spec.get('display_name', name)
                language = getattr(spec, 'language', 'unknown') if hasattr(spec, 'language') else spec.get('language', 'unknown')
                
                env_dict = getattr(spec, 'env', {}) if hasattr(spec, 'env') else spec.get('env', {})
                env_str = "; ".join([f"{k}={v}" for k, v in env_dict.items()]) if env_dict else "none"
                if len(env_str) > 60:
                    env_str = env_str[:57] + "..."

                available_specs.append({
                    "name": name,
                    "display_name": display_name,
                    "language": language,
                    "env": env_str,
                })

            # 2. Fetch Active Kernels
            active_kernels = []
            kernels = server_client.kernels.list_kernels() or []
            
            for kernel in kernels:
                k_id = getattr(kernel, 'id', 'unknown')
                k_name = getattr(kernel, 'name', 'unknown')
                state = getattr(kernel, 'execution_state', getattr(kernel, 'state', 'unknown'))
                connections = str(getattr(kernel, 'connections', '0'))
                
                last_act = getattr(kernel, 'last_activity', None)
                if last_act and hasattr(last_act, 'strftime'):
                    last_act_str = last_act.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    last_act_str = str(last_act) if last_act else "unknown"

                active_kernels.append({
                    "id": k_id,
                    "name": k_name,
                    "state": state,
                    "connections": connections,
                    "last_activity": last_act_str,
                })

            return available_specs, active_kernels

        except Exception as e:
            raise RuntimeError(f"Error fetching kernels info via HTTP: {str(e)}")

    async def _get_kernels_info_local(
        self, kernel_manager: Any, kernel_spec_manager: Any
    ) -> tuple[List[Dict[str, str]], List[Dict[str, str]]]:
        """Fetch active kernels and available specs using local managers (JUPYTER_SERVER mode)."""
        try:
            # 1. Fetch Available Kernel Specs
            available_specs = []
            raw_specs = kernel_spec_manager.get_all_specs() if kernel_spec_manager else {}
            
            for name, spec_info in raw_specs.items():
                spec = spec_info.get('spec', {})
                display_name = spec.get('display_name', name)
                language = spec.get('language', 'unknown')
                
                env_dict = spec.get('env', {})
                env_str = "; ".join([f"{k}={v}" for k, v in env_dict.items()]) if env_dict else "none"
                if len(env_str) > 60:
                    env_str = env_str[:57] + "..."

                available_specs.append({
                    "name": name,
                    "display_name": display_name,
                    "language": language,
                    "env": env_str,
                })

            # 2. Fetch Active Kernels
            active_kernels = []
            running_kernels = list(kernel_manager.list_kernels()) if kernel_manager else []
            
            for k_info in running_kernels:
                last_act = k_info.get('last_activity')
                if last_act and hasattr(last_act, 'strftime'):
                    last_act_str = last_act.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    last_act_str = str(last_act) if last_act else "unknown"

                active_kernels.append({
                    "id": k_info.get('id', 'unknown'),
                    "name": k_info.get('name', 'unknown'),
                    "state": k_info.get('execution_state', 'unknown'),
                    "connections": str(k_info.get('connections', '0')),
                    "last_activity": last_act_str,
                })

            return available_specs, active_kernels

        except Exception as e:
            raise RuntimeError(f"Error fetching kernels info locally: {str(e)}")

    async def execute(
        self,
        mode: ServerMode,
        server_client: Optional[JupyterServerClient] = None,
        kernel_client: Optional[Any] = None,
        contents_manager: Optional[Any] = None,
        kernel_manager: Optional[Any] = None,
        kernel_spec_manager: Optional[Any] = None,
        **kwargs
    ) -> str:
        """List all available kernel specs and currently active kernels.
        
        Args:
            mode: Server mode (MCP_SERVER or JUPYTER_SERVER)
            server_client: HTTP client for MCP_SERVER mode
            kernel_manager: Kernel manager access for JUPYTER_SERVER mode
            kernel_spec_manager: Kernel spec manager for JUPYTER_SERVER mode
            **kwargs: Additional parameters
            
        Returns:
            Formatted strings containing available kernel specs and running kernels.
        """
        # Get kernel specs and active kernels based on mode
        if mode == ServerMode.JUPYTER_SERVER and (kernel_manager is not None or kernel_spec_manager is not None):
            available_specs, active_kernels = await self._get_kernels_info_local(kernel_manager, kernel_spec_manager)
        elif mode == ServerMode.MCP_SERVER and server_client is not None:
            available_specs, active_kernels = self._get_kernels_info_http(server_client)
        else:
            raise ValueError(f"Invalid mode or missing required managers/clients: mode={mode}")

        sections = []

        # Format Section 1: Available Kernel Specs
        sections.append("=== Available Kernel Specs (Can be used to create/start new kernels) ===")
        if available_specs:
            spec_headers = ["Name (kernel_name)", "Display_Name", "Language", "Environment"]
            spec_rows = [
                [s["name"], s["display_name"], s["language"], s["env"]]
                for s in available_specs
            ]
            sections.append(format_TSV(spec_headers, spec_rows))
        else:
            sections.append("No kernel specs found.")

        sections.append("\n" + "=" * 60 + "\n")

        # Format Section 2: Active Kernels
        sections.append("=== Active Running Kernels ===")
        if active_kernels:
            active_headers = ["ID (kernel_id)", "Spec_Name", "State", "Connections", "Last_Activity"]
            active_rows = [
                [k["id"], k["name"], k["state"], k["connections"], k["last_activity"]]
                for k in active_kernels
            ]
            sections.append(format_TSV(active_headers, active_rows))
        else:
            sections.append("(No active kernels currently running)")

        return "\n".join(sections)

