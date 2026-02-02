package board;

import java.io.IOException;
import javax.servlet.ServletException;
import javax.servlet.annotation.WebServlet;
import javax.servlet.http.HttpServlet;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;

@WebServlet("/BoardRewriteCon.do")
public class BoardRewriteCon extends HttpServlet {
	private static final long serialVersionUID = 1L;

	public BoardRewriteCon() {
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
		
		//원글 받아야하는 것이 먼저
		
		int NUM = Integer.parseInt(request.getParameter("NUM"));
		int REF = Integer.parseInt(request.getParameter("REF"));
		int RE_STEP = Integer.parseInt(request.getParameter("RE_STEP"));
		int RE_LEVEL = Integer.parseInt(request.getParameter("RE_LEVEL"));
	
		BoardDAO bdao = new BoardDAO();
		BoardDTO bean = bdao.getOneUpdateBoard(NUM);
		
	}
}
