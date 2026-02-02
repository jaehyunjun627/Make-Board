package board;

import java.io.IOException;

import javax.servlet.RequestDispatcher;
import javax.servlet.ServletException;
import javax.servlet.annotation.WebServlet;
import javax.servlet.http.HttpServlet;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;

@WebServlet("/BoardDeleteProcCon.do")
public class BoardDeleteProcCon extends HttpServlet {
	private static final long serialVersionUID = 1L;

	protected void doGet(HttpServletRequest request, HttpServletResponse response)
			throws ServletException, IOException {
		reqPro(request, response);
	}

	protected void doPost(HttpServletRequest request, HttpServletResponse response)
			throws ServletException, IOException {
		reqPro(request, response);
	}

	protected void reqPro(HttpServletRequest request, HttpServletResponse response)
			throws ServletException, IOException {
		request.setCharacterEncoding("utf-8");

		int num = Integer.parseInt(request.getParameter("NUM"));
		String pass = request.getParameter("pass"); // 오타 있으면 여기일지도!!!!
		String password = request.getParameter("PASSWORD"); // 오타 있으면 여기일지도!!!!

		if (pass.equals(password)) {
			BoardDAO bdao = new BoardDAO();
			bdao.deleteBoard(num);

			response.sendRedirect("BoardListCon.do");
		} else {
			request.setAttribute("msg", "1");
		}


	}

}
