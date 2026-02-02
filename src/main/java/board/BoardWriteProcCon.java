package board;

import java.io.IOException;

import javax.servlet.RequestDispatcher;
import javax.servlet.ServletException;
import javax.servlet.annotation.WebServlet;
import javax.servlet.http.HttpServlet;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;

@WebServlet("/BoardWriteProcCon.do")
public class BoardWriteProcCon extends HttpServlet {
	private static final long serialVersionUID = 1L;

	public BoardWriteProcCon() {
		super();
	}

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

		// jsp(front)

		BoardDTO bean = new BoardDTO();

		bean.setWriter(request.getParameter("writer"));
		bean.setSUBJECT(request.getParameter("subject"));
		bean.setEmail(request.getParameter("email"));
		bean.setPASSWORD(request.getParameter("password"));
		bean.setCONTENT(request.getParameter("content"));
		
		//model(database)
		
		BoardDAO bdao = new BoardDAO();
		bdao.insertBoard(bean);
		
		//글쓰기 완료 후 
		response.sendRedirect("BoardListCon.do");
		

	}
}