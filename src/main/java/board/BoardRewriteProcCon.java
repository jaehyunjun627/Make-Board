package board;

import java.io.IOException;
import javax.servlet.ServletException;
import javax.servlet.annotation.WebServlet;
import javax.servlet.http.HttpServlet;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;

@WebServlet("/BoardRewriteProcCon.do")
public class BoardRewriteProcCon extends HttpServlet {
	private static final long serialVersionUID = 1L;

	public BoardRewriteProcCon() {
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

		// 원글 받아야하는 것이 먼저

		request.setCharacterEncoding("utf-8");

		// ============ 원글 정보 (답글 위치 계산용) ============
		int NUM = Integer.parseInt(request.getParameter("NUM")); // 여기 주의!!!!!!!!!!!
		int REF = Integer.parseInt(request.getParameter("REF")); // 여기 주의!!!!!!!!!!!
		int RE_STEP = Integer.parseInt(request.getParameter("RE_STEP")); // 여기 주의!!!!!!!!!!!
		int RE_LEVEL = Integer.parseInt(request.getParameter("RE_LEVEL")); // 여기 주의!!!!!!!!!!!

		String writer = request.getParameter("writer");
		String SUBJECT = request.getParameter("SUBJECT");
		String email = request.getParameter("email");
		String PASSWORD = request.getParameter("PASSWORD");
		String CONTENT = request.getParameter("CONTENT");

		// dto에 데이터 답기

		BoardDTO bean = new BoardDTO();
		bean.setWriter(writer);
		bean.setSUBJECT(SUBJECT);
		bean.setEmail(email);
		bean.setPASSWORD(PASSWORD);
		bean.setCONTENT(CONTENT);

		BoardDAO bdao = new BoardDAO();
		bdao.insertReply(bean, REF, RE_STEP, RE_LEVEL);
		
		response.sendRedirect("BoardListCon.do");
	}
}
